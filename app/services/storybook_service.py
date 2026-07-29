from __future__ import annotations

import base64
import binascii
import mimetypes
from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.datastructures import Headers, UploadFile as StarletteUploadFile

from app.core.config import BASE_DIR, settings
from app.models.storybook import Storybook, StorybookStatus, StoryPage
from app.models.user import User, UserRole
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.workout_plan_repository import WorkoutPlanCompletionRepository
from app.repositories.daily_goal_repository import DailyGoalCompletionRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.models.nutrition_plan import NutritionPlan, nutrition_plan_valid_until
from app.models.routine import Routine
from app.repositories.routine_repository import RoutineRepository
from app.repositories.routine_macro_log_repository import RoutineMacroLogRepository
from app.repositories.storybook_repository import StorybookRepository, StoryPageRepository
from app.repositories.user_repository import UserRepository
from app.schemas.ai import RegenerateImageRequest, RegeneratePageRequest, StorybookGenerateRequest
from app.core.logging import get_logger
from app.services.weekly_summary_service import WeeklySummaryService
from app.services.ai_service import (
    AIService,
    AIServiceConfigError,
    AIServiceConnectionError,
    AIServiceError,
    AIServiceResponseError,
    AIServiceTimeoutError,
)

logger = get_logger(__name__)


class StorybookServiceError(Exception):
    pass


class StorybookNotFoundError(StorybookServiceError):
    pass


class StoryPageNotFoundError(StorybookServiceError):
    pass


class StorybookAccessError(StorybookServiceError):
    pass


class StorybookValidationError(StorybookServiceError):
    pass


@dataclass(frozen=True)
class StorybookContext:
    routine_summary: str | None
    workout_plan_summary: str | None
    nutrition_plan_summary: str | None


@dataclass(frozen=True)
class StorybookGenerationJob:
    storybook_id: UUID
    payload: StorybookGenerateRequest
    selfie_bytes: bytes
    selfie_filename: str
    selfie_content_type: str
    target_date: date | None = None
    timezone: str | None = None
    mode: str | None = "PLAN"
    context_json: str | None = None


class StorybookService:
    _AI_GENDER_VALUES = {"Male", "Female", "Other", "Prefer Not To Say"}
    _AI_FITNESS_GOAL_VALUES = {
        "Weight Loss",
        "Muscle Gain",
        "Strength Building",
        "General Fitness",
        "Athletic Performance",
    }
    _AI_MEAL_TYPE_VALUES = {"BREAKFAST", "LUNCH", "DINNER", "SNACK"}
    _AI_SELFIE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

    def __init__(
        self,
        *,
        db: Session,
        ai_service: AIService,
        storybook_repository: StorybookRepository,
        story_page_repository: StoryPageRepository,
        routine_repository: RoutineRepository,
        nutrition_plan_repository: NutritionPlanRepository,
        routine_macro_log_repository: RoutineMacroLogRepository | None = None,
        user_repository: UserRepository,
        coach_client_repository: CoachClientRepository,
    ) -> None:
        self.db = db
        self.ai_service = ai_service
        self.storybook_repository = storybook_repository
        self.story_page_repository = story_page_repository
        self.routine_repository = routine_repository
        self.nutrition_plan_repository = nutrition_plan_repository
        self.routine_macro_log_repository = (
            routine_macro_log_repository or RoutineMacroLogRepository(db)
        )
        self.user_repository = user_repository
        self.coach_client_repository = coach_client_repository

    async def create_storybook_generation(
        self,
        *,
        current_coach: User,
        client_id: UUID,
        selfie: UploadFile | None,
        wake_up_time: str | None,
        bed_time: str | None,
        image_style: str | None,
        name: str | None,
        age: int | None,
        gender: str | None,
        fitness_goal: str | None,
        height: str | None,
        weight: float | None,
        target_weight: float | None,
        bio: str | None,
        fitness_motivation: str | None,
    ) -> StorybookGenerationJob:
        if current_coach.role != UserRole.COACH:
            raise StorybookAccessError("Coach role required for storybook generation")

        if not self.coach_client_repository.accepted_relationship_exists(
            coach_id=current_coach.id,
            client_id=client_id,
        ):
            raise StorybookAccessError("Coach is not assigned to this client")

        profile = self.user_repository.get_by_id(client_id)
        if profile is None:
            raise StorybookValidationError("User profile not found")

        name_value = name or profile.full_name
        derived_profile_age = self._calculate_age(profile.date_of_birth)
        age_value = age if age is not None else derived_profile_age
        gender_value = gender or profile.gender
        fitness_goal_value = fitness_goal or profile.fitness_goal

        # Default wake/bed time if not provided; other fields are derived from profile
        wake_time_value = wake_up_time or "07:00"
        bed_time_value = bed_time or "22:00"

        # Resolve due date and enforce a 7-day generation window.
        today = date.today()
        target = today

        active_plan = self.nutrition_plan_repository.get_active_by_client_date(
            client_id=client_id,
            plan_date=target,
        )
        if active_plan is None:
            raise StorybookValidationError("No active nutrition plan for the target date")

        context = self._build_context(user_id=client_id, plan_date=target)
        combined_bio = bio or self._build_bio(profile=profile, context=context)
        motivation_value = fitness_motivation or profile.fitness_goal

        storybook = Storybook(
            user_id=client_id,
            date=target,
            status=StorybookStatus.PENDING,
        )
        self.storybook_repository.create(storybook=storybook, commit=True)

        try:
            payload = StorybookGenerateRequest(
                name=name_value or profile.full_name or "User",
                age=age_value or 18,
                gender=gender_value or "UNSPECIFIED",
                fitness_goal=fitness_goal_value or "GENERAL_FITNESS",
                wake_up_time=wake_time_value,
                bed_time=bed_time_value,
                height=height,
                weight=weight,
                target_weight=target_weight,
                bio=combined_bio,
                fitness_motivation=motivation_value,
                image_style=image_style or "ghibli_animation",
                routine_summary=context.routine_summary,
                workout_plan_summary=context.workout_plan_summary,
                nutrition_plan_summary=context.nutrition_plan_summary,
            )
        except ValidationError as exc:
            self._mark_storybook_failed(storybook=storybook)
            raise StorybookValidationError(str(exc)) from exc

        try:
            resolved_selfie = await self._resolve_generation_selfie(profile=profile, selfie=selfie)
            selfie_bytes = await resolved_selfie.read()
        except StorybookValidationError:
            self._mark_storybook_failed(storybook=storybook)
            raise

        if not selfie_bytes:
            self._mark_storybook_failed(storybook=storybook)
            raise StorybookValidationError("Selfie image is empty")

        selfie_filename = resolved_selfie.filename or "selfie.png"
        selfie_content_type = (
            self._detect_image_content_type(selfie_bytes)
            or resolved_selfie.content_type
            or self._guess_content_type(selfie_filename)
        )
        if selfie_content_type not in self._AI_SELFIE_CONTENT_TYPES:
            self._mark_storybook_failed(storybook=storybook)
            raise StorybookValidationError("Selfie image must be JPG, PNG, or WebP")

        return StorybookGenerationJob(
            storybook_id=storybook.id,
            payload=payload,
            selfie_bytes=selfie_bytes,
            selfie_filename=selfie_filename,
            selfie_content_type=selfie_content_type,
            target_date=target,
            timezone="UTC",
            mode="PLAN",
        )

    async def process_storybook_generation(self, *, job: StorybookGenerationJob) -> None:
        storybook = self.storybook_repository.get_by_id(storybook_id=job.storybook_id)
        if storybook is None:
            return

        if storybook.status == StorybookStatus.COMPLETED:
            return

        selfie_file = self._make_upload_file(
            file_bytes=job.selfie_bytes,
            filename=job.selfie_filename,
            content_type=job.selfie_content_type,
        )

        try:
            if job.context_json:
                response = await self.ai_service.generate_storybook_from_backend(
                    context_json=job.context_json,
                    selfie=selfie_file,
                )
            else:
                context_json = self._build_backend_context_json(
                    storybook=storybook,
                    job=job,
                )
                response = await self.ai_service.generate_storybook_from_backend(
                    context_json=context_json,
                    selfie=selfie_file,
                )
        except (
            AIServiceTimeoutError,
            AIServiceConnectionError,
            AIServiceResponseError,
            AIServiceConfigError,
            AIServiceError,
        ) as exc:
            logger.warning(
                "storybook_generation_failed",
                storybook_id=str(storybook.id),
                error_type=type(exc).__name__,
                error=str(exc),
            )
            self._mark_storybook_failed(storybook=storybook)
            return

        ai_book_id = self._extract_ai_book_id(response)
        pdf_url = self._normalize_ai_asset_url(self._extract_pdf_url(response))
        pages = [
            _StoryPagePayload(
                page_number=page.page_number,
                story=page.story,
                image_url=self._normalize_ai_asset_url(page.image_url),
            )
            for page in self._extract_pages(response)
        ]

        now = datetime.now(tz=timezone.utc)
        updates = {
            "status": StorybookStatus.COMPLETED,
            "generated_at": now,
            "pdf_url": pdf_url,
            "ai_book_id": ai_book_id,
        }

        try:
            self.storybook_repository.update_fields(
                storybook=storybook,
                updates=updates,
                commit=False,
            )
            story_pages = [
                StoryPage(
                    storybook_id=storybook.id,
                    page_number=page.page_number,
                    story=page.story,
                    image_url=page.image_url,
                    is_edited=False,
                )
                for page in pages
            ]
            self.story_page_repository.add_pages(pages=story_pages, commit=False)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.exception(
                "storybook_generation_persist_failed",
                storybook_id=str(storybook.id),
                error_type=type(exc).__name__,
                error=str(exc),
            )
            self._mark_storybook_failed(storybook=storybook)
            return

    def get_storybook(self, *, current_user: User, storybook_id: UUID) -> tuple[Storybook, list[StoryPage]]:
        storybook = self._get_storybook_or_error(storybook_id=storybook_id)
        self._ensure_storybook_access(current_user=current_user, storybook=storybook)
        pages = self.story_page_repository.list_by_storybook(storybook_id=storybook.id)
        return storybook, pages

    def get_storybook_page(
        self,
        *,
        current_user: User,
        storybook_id: UUID,
        page_number: int,
    ) -> StoryPage:
        storybook = self._get_storybook_or_error(storybook_id=storybook_id)
        self._ensure_storybook_access(current_user=current_user, storybook=storybook)
        page = self.story_page_repository.get_by_storybook_and_page(
            storybook_id=storybook.id,
            page_number=page_number,
        )
        if page is None:
            raise StoryPageNotFoundError("Storybook page not found")
        return page

    def update_story_page(
        self,
        *,
        current_user: User,
        storybook_id: UUID,
        page_number: int,
        story: str,
    ) -> StoryPage:
        page = self.get_storybook_page(
            current_user=current_user,
            storybook_id=storybook_id,
            page_number=page_number,
        )
        updates = {"story": story, "is_edited": True}
        return self.story_page_repository.update_fields(page=page, updates=updates, commit=True)

    def get_storybook_status(self, *, current_user: User, storybook_id: UUID) -> StorybookStatus:
        storybook = self._get_storybook_or_error(storybook_id=storybook_id)
        self._ensure_storybook_access(current_user=current_user, storybook=storybook)
        return storybook.status

    async def regenerate_story(
        self,
        *,
        current_user: User,
        storybook_id: UUID,
        page_number: int,
        payload: RegeneratePageRequest | None,
    ) -> StoryPage:
        storybook = self._get_storybook_or_error(storybook_id=storybook_id)
        self._ensure_storybook_access(current_user=current_user, storybook=storybook)
        page = self._get_page_or_error(storybook_id=storybook_id, page_number=page_number)
        ai_payload = payload or RegeneratePageRequest(
            story_text=page.story or "Regenerate story text",
        )

        response = await self.ai_service.regenerate_page(
            book_id=self._require_ai_book_id(storybook),
            page_number=page_number,
            payload=ai_payload,
        )
        updated_story = self._extract_story_text(response)
        if updated_story is None:
            raise StorybookServiceError("AI response missing story text")

        updates = {"story": updated_story, "is_edited": True}
        return self.story_page_repository.update_fields(page=page, updates=updates, commit=True)

    async def regenerate_image(
        self,
        *,
        current_user: User,
        storybook_id: UUID,
        page_number: int,
        payload: RegenerateImageRequest | None,
    ) -> StoryPage:
        storybook = self._get_storybook_or_error(storybook_id=storybook_id)
        self._ensure_storybook_access(current_user=current_user, storybook=storybook)
        page = self._get_page_or_error(storybook_id=storybook_id, page_number=page_number)
        ai_payload = payload or RegenerateImageRequest(
            image_prompt=page.story or "Storybook illustration",
            image_style=None,
        )

        response = await self.ai_service.regenerate_image(
            book_id=self._require_ai_book_id(storybook),
            page_number=page_number,
            payload=ai_payload,
        )
        image_url = self._normalize_ai_asset_url(self._extract_image_url(response))
        if image_url is None:
            raise StorybookServiceError("AI response missing image url")

        updates = {"image_url": image_url}
        return self.story_page_repository.update_fields(page=page, updates=updates, commit=True)

    async def regenerate_story_and_image(
        self,
        *,
        current_user: User,
        storybook_id: UUID,
        page_number: int,
        payload: RegeneratePageRequest | None,
    ) -> StoryPage:
        storybook = self._get_storybook_or_error(storybook_id=storybook_id)
        self._ensure_storybook_access(current_user=current_user, storybook=storybook)
        page = self._get_page_or_error(storybook_id=storybook_id, page_number=page_number)
        ai_payload = payload or RegeneratePageRequest(
            story_text=page.story or "Regenerate story and image",
        )

        response = await self.ai_service.regenerate_page(
            book_id=self._require_ai_book_id(storybook),
            page_number=page_number,
            payload=ai_payload,
        )
        updated_story = self._extract_story_text(response)
        image_url = self._normalize_ai_asset_url(self._extract_image_url(response))
        if updated_story is None or image_url is None:
            raise StorybookServiceError("AI response missing regenerated content")

        updates = {"story": updated_story, "image_url": image_url, "is_edited": True}
        return self.story_page_repository.update_fields(page=page, updates=updates, commit=True)

    def get_pdf_url(self, *, current_user: User, storybook_id: UUID) -> str:
        storybook = self._get_storybook_or_error(storybook_id=storybook_id)
        self._ensure_storybook_access(current_user=current_user, storybook=storybook)
        if not storybook.pdf_url:
            raise StorybookNotFoundError("Storybook PDF not available")
        return storybook.pdf_url

    # Backend-to-backend context
    def _build_backend_context_json(self, *, storybook: Storybook, job: StorybookGenerationJob) -> str:
        import json

        owner = self.user_repository.get_by_id(storybook.user_id)
        target = job.target_date or storybook.date or date.today()
        plan = self.nutrition_plan_repository.get_active_by_client_date(
            client_id=storybook.user_id,
            plan_date=target,
        )
        routine = self.routine_repository.get_by_user_and_date(
            user_id=storybook.user_id,
            routine_date=target,
        )
        logs = (
            self.routine_macro_log_repository.list_by_routine_for_user(
                routine_id=routine.id, user_id=storybook.user_id
            )
            if routine
            else []
        )
        # Weekly summaries
        weekly = WeeklySummaryService(
            routine_repository=self.routine_repository,
            routine_macro_log_repository=self.routine_macro_log_repository,
            workout_plan_repository=self._workout_repo_for_context(),
            daily_goal_repository=self._goal_repo_for_context(),
            nutrition_plan_repository=self.nutrition_plan_repository,
            user_repository=self.user_repository,
            coach_client_repository=self.coach_client_repository,
        )
        aggregate = weekly.get_current_week_analytics(current_user=owner)
        workouts = weekly.get_current_week_workouts(current_user=owner)
        goals = weekly.get_current_week_goals(current_user=owner)
        workout_day = next((d for d in workouts.days if d.date == target), None)
        goal_day = next((d for d in goals.days if d.date == target), None)

        context = {
            "schema_version": "daily-story-context.v1",
            "storybook_id": str(storybook.id),
            "target_date": str(target),
            "timezone": job.timezone or "UTC",
            "mode": job.mode or "PLAN",
            "profile": {
                "full_name": self._normalize_full_name(
                    job.payload.name if job.payload else (owner.full_name if owner else None)
                ),
                "age": self._normalize_age(
                    (job.payload.age if job.payload else None)
                    or (self._calculate_age(owner.date_of_birth) if owner else None)
                ),
                "gender": self._normalize_ai_gender(
                    job.payload.gender if job.payload else (owner.gender if owner else None)
                ),
                "fitness_goal": self._normalize_ai_fitness_goal(
                    job.payload.fitness_goal if job.payload else (owner.fitness_goal if owner else None)
                ),
                "wake_up_time": (job.payload.wake_up_time if job.payload else None) or "07:00",
                "bed_time": (job.payload.bed_time if job.payload else None) or "22:00",
                "short_bio": job.payload.bio if job.payload else None,
                "fitness_motivation": job.payload.fitness_motivation if job.payload else None,
            },
            "nutrition_plan": {
                "id": str(plan.id) if plan else None,
                "daily_calories": self._non_negative(plan.daily_calories if plan else None),
                "protein": self._non_negative(plan.protein if plan else None),
                "carbs": self._non_negative(plan.carbs if plan else None),
                "fat": self._non_negative(plan.fat if plan else None),
                "fiber": self._non_negative(plan.fiber if plan else None),
                "water_goal": self._non_negative(plan.water_goal if plan else None),
                "water_unit": "ml",
                "workout_plan": list(plan.workout_plan or []) if plan else [],
                "daily_goals": list(plan.daily_goals or []) if plan else [],
                "meal_targets": [],
                "notes": plan.notes if plan else None,
                "date": str(plan.date) if plan else None,
                "valid_from": str(plan.date) if plan else None,
                "valid_until": str(nutrition_plan_valid_until(plan.date)) if plan else None,
            },
            "routine_dashboard": self._build_routine_dashboard(plan=plan, routine=routine, logs=logs),
            "workout_summary": {
                "days": [
                    {
                        "date": str(workout_day.date),
                        "is_future": False,
                        "applicable": True,
                        "items": [
                            {
                                "id": str(item.id),
                                "position": item.position,
                                "instruction": item.instruction,
                                "scheduled_time": None,
                                "completed": item.completed,
                            }
                            for item in (workout_day.items if workout_day else [])
                        ],
                    }
                ]
                if workout_day
                else {"days": []}
            },
            "goal_summary": {
                "days": [
                    {
                        "date": str(goal_day.date),
                        "is_future": False,
                        "applicable": True,
                        "items": [
                            {
                                "id": str(item.id),
                                "position": item.position,
                                "instruction": item.instruction,
                                "completed": item.completed,
                            }
                            for item in (goal_day.items if goal_day else [])
                        ],
                    }
                ]
                if goal_day
                else {"days": []}
            },
            "weekly_summary": {
                "weekly_progress_percentage": self._clamp_percentage(aggregate.weekly_progress_percentage),
            },
            "generation": {
                "page_count": 10,
                "image_style": (job.payload.image_style if job.payload else None) or "premium_wellness",
            },
        }
        return json.dumps(context, default=str)

    def _workout_repo_for_context(self) -> WorkoutPlanCompletionRepository:
        # Reuse existing session-bound repository
        return WorkoutPlanCompletionRepository(self.db)

    def _goal_repo_for_context(self) -> DailyGoalCompletionRepository:
        return DailyGoalCompletionRepository(self.db)

    async def _resolve_generation_selfie(self, *, profile: User, selfie: UploadFile | None) -> UploadFile:
        if selfie is not None:
            uploaded_bytes = await selfie.read()
            await selfie.seek(0)
            if uploaded_bytes:
                return selfie

        for image_url in self._preferred_profile_image_urls(profile=profile):
            loaded = await self._load_selfie_from_image_url(image_url=image_url)
            if loaded is not None:
                return loaded

        raise StorybookValidationError(
            "Selfie image is required. Upload a selfie or save a profile/reference image first"
        )

    @staticmethod
    def _preferred_profile_image_urls(*, profile: User) -> list[str]:
        primary = profile.reference_image if profile.use_reference_image else profile.profile_image
        secondary = profile.profile_image if profile.use_reference_image else profile.reference_image
        return [value for value in (primary, secondary) if isinstance(value, str) and value.strip()]

    async def _load_selfie_from_image_url(self, *, image_url: str) -> UploadFile | None:
        decoded = self._decode_base64_image(image_url)
        if decoded is not None:
            file_bytes, filename, content_type = decoded
            return self._make_upload_file(
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
            )

        local_path = self._resolve_local_media_path(image_url=image_url)
        if local_path is not None and local_path.is_file():
            file_bytes = local_path.read_bytes()
            if not file_bytes:
                return None
            return self._make_upload_file(
                file_bytes=file_bytes,
                filename=local_path.name,
                content_type=self._guess_content_type(local_path.name),
            )

        parsed = urlparse(image_url)
        if parsed.scheme not in {"http", "https"}:
            return None

        try:
            timeout = httpx.Timeout(settings.ai_backend_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(image_url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        file_bytes = response.content
        if not file_bytes:
            return None

        filename = Path(parsed.path).name or "selfie.png"
        content_type = response.headers.get("content-type", "").split(";", maxsplit=1)[0].strip()
        if not content_type:
            content_type = self._guess_content_type(filename)

        return self._make_upload_file(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
        )

    def _resolve_local_media_path(self, *, image_url: str) -> Path | None:
        if settings.storage_backend.strip().lower() != "local":
            return None

        parsed = urlparse(image_url)
        media_path = parsed.path if parsed.scheme in {"http", "https"} else image_url
        if not media_path:
            return None

        media_prefix = settings.local_media_url_prefix.strip()
        if not media_prefix.startswith("/"):
            media_prefix = f"/{media_prefix}"
        media_prefix = media_prefix.rstrip("/")

        object_key: str | None = None
        if media_prefix and media_path.startswith(f"{media_prefix}/"):
            object_key = media_path[len(media_prefix) + 1 :]
        elif not parsed.scheme:
            object_key = media_path.lstrip("/")

        if not object_key:
            return None

        relative_path = Path(object_key)
        if relative_path.is_absolute() or any(part == ".." for part in relative_path.parts):
            return None

        return BASE_DIR / settings.local_storage_dir / relative_path

    @staticmethod
    def _guess_content_type(filename: str) -> str:
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"

    @staticmethod
    def _decode_base64_image(value: str) -> tuple[bytes, str, str] | None:
        raw = value.strip()
        if not raw:
            return None

        content_type: str | None = None
        payload = raw

        if raw.startswith("data:"):
            prefix, sep, remainder = raw.partition(",")
            if sep != "," or ";base64" not in prefix.lower():
                return None
            payload = remainder.strip()
            content_type = prefix[5:].split(";", maxsplit=1)[0].strip() or None

        compact = "".join(payload.split())
        try:
            image_bytes = base64.b64decode(compact, validate=True)
        except (ValueError, binascii.Error):
            return None

        if not image_bytes:
            return None

        detected_type = StorybookService._detect_image_content_type(image_bytes)
        final_content_type = detected_type or content_type or "application/octet-stream"
        extension = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }.get(final_content_type, ".bin")
        return image_bytes, f"selfie{extension}", final_content_type

    @staticmethod
    def _detect_image_content_type(image_bytes: bytes) -> str | None:
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
            return "image/gif"
        if len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            return "image/webp"
        return None

    @staticmethod
    def _normalize_full_name(value: str | None) -> str:
        normalized = (value or "").strip()
        return normalized if len(normalized) >= 2 else "User"

    @staticmethod
    def _normalize_age(value: int | None) -> int:
        if value is None:
            return 18
        return min(120, max(13, int(value)))

    @classmethod
    def _normalize_ai_gender(cls, value: str | None) -> str:
        if not value:
            return "Prefer Not To Say"
        lowered = value.strip().lower().replace("_", " ")
        mapping = {
            "male": "Male",
            "female": "Female",
            "other": "Other",
            "prefer not to say": "Prefer Not To Say",
            "unspecified": "Prefer Not To Say",
            "unknown": "Prefer Not To Say",
        }
        mapped = mapping.get(lowered)
        return mapped if mapped in cls._AI_GENDER_VALUES else "Prefer Not To Say"

    @classmethod
    def _normalize_ai_fitness_goal(cls, value: str | None) -> str:
        if not value:
            return "General Fitness"
        lowered = value.strip().lower().replace("_", " ")
        mapping = {
            "weight loss": "Weight Loss",
            "muscle gain": "Muscle Gain",
            "strength building": "Strength Building",
            "general fitness": "General Fitness",
            "athletic performance": "Athletic Performance",
        }
        mapped = mapping.get(lowered)
        return mapped if mapped in cls._AI_FITNESS_GOAL_VALUES else "General Fitness"

    @classmethod
    def _normalize_ai_meal_type(cls, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip().upper().replace(" ", "_")
        return normalized if normalized in cls._AI_MEAL_TYPE_VALUES else None

    @staticmethod
    def _non_negative(value: Any) -> float:
        if value is None:
            return 0.0
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        if numeric < 0:
            return 0.0
        return numeric

    @staticmethod
    def _clamp_percentage(value: Any) -> float:
        numeric = StorybookService._non_negative(value)
        return 100.0 if numeric > 100.0 else numeric

    @staticmethod
    def _make_upload_file(*, file_bytes: bytes, filename: str, content_type: str) -> UploadFile:
        normalized_content_type = content_type or "application/octet-stream"
        return UploadFile(
            BytesIO(file_bytes),
            filename=filename,
            headers=Headers({"content-type": normalized_content_type}),
        )

    def _build_routine_dashboard(
        self,
        *,
        plan: NutritionPlan | None,
        routine: Routine | None,
        logs: list[StarletteUploadFile] | list | None,
    ) -> dict[str, object]:
        totals = {
            "kcal": float(routine.meals_kcal or 0.0) if routine else 0.0,
            "protein": float(routine.intake_protein or 0.0) if routine else 0.0,
            "carbs": float(routine.intake_carbs or 0.0) if routine else 0.0,
            "fat": float(routine.intake_fats or 0.0) if routine else 0.0,
            "fiber": float(routine.intake_fiber or 0.0) if routine else 0.0,
            "water": float(routine.water_intake or 0.0) if routine else 0.0,
        }
        remaining = {
            "kcal": self._non_negative((float(plan.daily_calories) - totals["kcal"]) if plan and plan.daily_calories is not None else 0.0),
            "protein": self._non_negative((float(plan.protein) - totals["protein"]) if plan and plan.protein is not None else 0.0),
            "carbs": self._non_negative((float(plan.carbs) - totals["carbs"]) if plan and plan.carbs is not None else 0.0),
            "fat": self._non_negative((float(plan.fat) - totals["fat"]) if plan and plan.fat is not None else 0.0),
            "fiber": self._non_negative((float(plan.fiber) - totals["fiber"]) if plan and plan.fiber is not None else 0.0),
            "water": self._non_negative((float(plan.water_goal) - totals["water"]) if plan and plan.water_goal is not None else 0.0),
        }

        logged_meals: list[dict[str, object]] = []
        for log in (logs or []):
            meal_type = self._normalize_ai_meal_type(getattr(log, "meal_type", None))
            food_name = (getattr(log, "food_name", None) or "").strip()
            if meal_type is None or not food_name:
                continue
            raw_amount = getattr(log, "amount", None)
            amount_value = None if raw_amount is None else self._non_negative(raw_amount)
            logged_meals.append(
                {
                    "id": str(getattr(log, "id", "")) or None,
                    "meal_type": meal_type,
                    "food_name": food_name,
                    "amount": amount_value,
                    "amount_unit": getattr(log, "amount_unit", None),
                    "kcal": self._non_negative(getattr(log, "kcal", None)),
                    "protein": self._non_negative(getattr(log, "protein", None)),
                    "carbs": self._non_negative(getattr(log, "carbs", None)),
                    "fat": self._non_negative(getattr(log, "fat", None)),
                    "fiber": self._non_negative(getattr(log, "fiber", None)),
                    "logged_at": getattr(log, "logged_at", None),
                }
            )
        return {
            "date": str(routine.date if routine else (plan.date if plan else date.today())),
            "routine": (
                {
                    "id": str(routine.id),
                    "water_intake": totals["water"],
                    "sleep": self._non_negative(routine.sleep),
                    "completion_status": bool(routine.completion_status),
                }
                if routine
                else None
            ),
            "totals": totals,
            "remaining": remaining,
            "logged_meals": logged_meals,
        }

    def _build_context(self, *, user_id: UUID, plan_date: date) -> StorybookContext:
        routine = self.routine_repository.get_by_user_and_date(
            user_id=user_id,
            routine_date=plan_date,
        )
        routine_summary = None
        if routine is not None:
            routine_summary = (
                f"Routine {routine.date}: workout={routine.workout or 'n/a'}, "
                f"meals={routine.meals or 'n/a'}, water={routine.water_intake or 'n/a'}, "
                f"sleep={routine.sleep or 'n/a'}"
            )

        workout_plan_summary = None
        nutrition_plan_summary = None
        plan = self.nutrition_plan_repository.get_active_by_client_date(
            client_id=user_id,
            plan_date=plan_date,
        )
        if plan is not None:
            if plan.workout_plan:
                workout_plan_summary = f"Assigned workout plan: {'; '.join(plan.workout_plan)}"
            nutrition_plan_summary = (
                f"Nutrition plan {plan.date}: calories={plan.daily_calories or 'n/a'}, "
                f"protein={plan.protein or 'n/a'}, carbs={plan.carbs or 'n/a'}, "
                f"fat={plan.fat or 'n/a'}, fiber={plan.fiber or 'n/a'}, "
                f"water={plan.water_goal or 'n/a'}, "
                f"workout={'; '.join(plan.workout_plan) or 'n/a'}, "
                f"daily goals={'; '.join(plan.daily_goals) or 'n/a'}"
            )

        return StorybookContext(
            routine_summary=routine_summary,
            workout_plan_summary=workout_plan_summary,
            nutrition_plan_summary=nutrition_plan_summary,
        )

    @staticmethod
    def _build_bio(*, profile: User, context: StorybookContext) -> str | None:
        parts = []
        if profile.occupation:
            parts.append(f"Occupation: {profile.occupation}")
        if profile.fitness_goal:
            parts.append(f"Goal: {profile.fitness_goal}")
        if context.routine_summary:
            parts.append(context.routine_summary)
        if context.workout_plan_summary:
            parts.append(context.workout_plan_summary)
        if context.nutrition_plan_summary:
            parts.append(context.nutrition_plan_summary)
        return "; ".join(parts) if parts else None

    @staticmethod
    def _calculate_age(date_of_birth: date | None) -> int | None:
        if date_of_birth is None:
            return None

        today = date.today()
        return today.year - date_of_birth.year - (
            (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
        )

    def _ensure_storybook_access(self, *, current_user: User, storybook: Storybook) -> None:
        if current_user.role == UserRole.ADMIN:
            return
        if storybook.user_id == current_user.id:
            return
        if current_user.role != UserRole.COACH:
            raise StorybookAccessError("Access to storybook is forbidden")
        if not self.coach_client_repository.relationship_exists(
            coach_id=current_user.id,
            client_id=storybook.user_id,
        ):
            raise StorybookAccessError("Access to storybook is forbidden")

    def _get_storybook_or_error(self, *, storybook_id: UUID) -> Storybook:
        storybook = self.storybook_repository.get_by_id(storybook_id=storybook_id)
        if storybook is None:
            raise StorybookNotFoundError("Storybook not found")
        return storybook

    def _get_page_or_error(self, *, storybook_id: UUID, page_number: int) -> StoryPage:
        page = self.story_page_repository.get_by_storybook_and_page(
            storybook_id=storybook_id,
            page_number=page_number,
        )
        if page is None:
            raise StoryPageNotFoundError("Storybook page not found")
        return page

    @staticmethod
    def _extract_ai_book_id(response: dict[str, Any]) -> str | None:
        for key in ("book_id", "storybook_id", "id"):
            value = response.get(key)
            if isinstance(value, str) and value:
                return value
        nested = response.get("storybook")
        if isinstance(nested, dict):
            value = nested.get("book_id") or nested.get("id")
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _extract_pdf_url(response: dict[str, Any]) -> str | None:
        value = response.get("pdf_url")
        if isinstance(value, str) and value:
            return value
        nested = response.get("storybook")
        if isinstance(nested, dict):
            nested_value = nested.get("pdf_url")
            if isinstance(nested_value, str) and nested_value:
                return nested_value
        return None

    @staticmethod
    def _extract_pages(response: dict[str, Any]) -> list[_StoryPagePayload]:
        pages_data = response.get("pages")
        if isinstance(pages_data, list):
            return [
                _StoryPagePayload.from_dict(page, index=index)
                for index, page in enumerate(pages_data)
            ]

        nested = response.get("storybook")
        if isinstance(nested, dict) and isinstance(nested.get("pages"), list):
            return [
                _StoryPagePayload.from_dict(page, index=index)
                for index, page in enumerate(nested.get("pages"))
            ]

        return []

    @staticmethod
    def _extract_story_text(response: dict[str, Any]) -> str | None:
        for key in ("story", "story_text", "text"):
            value = response.get(key)
            if isinstance(value, str):
                return value
        nested = response.get("page")
        if isinstance(nested, dict):
            for key in ("story", "story_text", "text"):
                value = nested.get(key)
                if isinstance(value, str):
                    return value
        return None

    @staticmethod
    def _extract_image_url(response: dict[str, Any]) -> str | None:
        for key in ("image_url", "image"):
            value = response.get(key)
            if isinstance(value, str):
                return value
        nested = response.get("page")
        if isinstance(nested, dict):
            value = nested.get("image_url") or nested.get("image")
            if isinstance(value, str):
                return value
        return None

    @staticmethod
    def _normalize_ai_asset_url(value: str | None) -> str | None:
        if not value:
            return None

        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"}:
            return value

        if not value.startswith("/"):
            return value

        base = settings.ai_backend_base_url.rstrip("/")
        parsed_base = urlparse(base)
        if not parsed_base.scheme or not parsed_base.netloc:
            return value
        return f"{parsed_base.scheme}://{parsed_base.netloc}{value}"

    @staticmethod
    def _require_ai_book_id(storybook: Storybook) -> str:
        if storybook.ai_book_id:
            return storybook.ai_book_id
        raise StorybookServiceError("Storybook AI reference is missing")

    def _mark_storybook_failed(self, *, storybook: Storybook) -> None:
        self.storybook_repository.update_fields(
            storybook=storybook,
            updates={"status": StorybookStatus.FAILED},
            commit=True,
        )


@dataclass(frozen=True)
class _StoryPagePayload:
    page_number: int
    story: str | None
    image_url: str | None

    @classmethod
    def from_dict(cls, raw: Any, *, index: int) -> "_StoryPagePayload":
        if not isinstance(raw, dict):
            return cls(page_number=index + 1, story=None, image_url=None)

        page_number = raw.get("page_number") or raw.get("page") or index + 1
        try:
            page_number_int = int(page_number)
        except (TypeError, ValueError):
            page_number_int = index + 1

        story = raw.get("story") or raw.get("story_text") or raw.get("text")
        image_url = raw.get("image_url") or raw.get("image")
        return cls(page_number=page_number_int, story=story, image_url=image_url)
