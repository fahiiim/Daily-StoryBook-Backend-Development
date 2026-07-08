from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.models.storybook import Storybook, StorybookStatus, StoryPage
from app.models.user import User, UserRole
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.storybook_repository import StorybookRepository, StoryPageRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_plan_repository import WorkoutPlanRepository
from app.schemas.ai import RegenerateImageRequest, RegeneratePageRequest, StorybookGenerateRequest
from app.services.ai_service import (
    AIService,
    AIServiceConfigError,
    AIServiceConnectionError,
    AIServiceError,
    AIServiceResponseError,
    AIServiceTimeoutError,
)


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


class StorybookService:
    def __init__(
        self,
        *,
        db: Session,
        ai_service: AIService,
        storybook_repository: StorybookRepository,
        story_page_repository: StoryPageRepository,
        routine_repository: RoutineRepository,
        nutrition_plan_repository: NutritionPlanRepository,
        workout_plan_repository: WorkoutPlanRepository,
        user_repository: UserRepository,
        coach_client_repository: CoachClientRepository,
    ) -> None:
        self.db = db
        self.ai_service = ai_service
        self.storybook_repository = storybook_repository
        self.story_page_repository = story_page_repository
        self.routine_repository = routine_repository
        self.nutrition_plan_repository = nutrition_plan_repository
        self.workout_plan_repository = workout_plan_repository
        self.user_repository = user_repository
        self.coach_client_repository = coach_client_repository

    async def create_storybook_generation(
        self,
        *,
        current_user: User,
        selfie: UploadFile,
        wake_up_time: str,
        bed_time: str,
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
        profile = self.user_repository.get_by_id(current_user.id)
        if profile is None:
            raise StorybookValidationError("User profile not found")

        name_value = name or profile.full_name
        derived_profile_age = self._calculate_age(profile.date_of_birth)
        age_value = age if age is not None else derived_profile_age
        gender_value = gender or profile.gender
        fitness_goal_value = fitness_goal or profile.fitness_goal

        missing_fields = []
        if not name_value:
            missing_fields.append("name")
        if age_value is None:
            missing_fields.append("age")
        if not gender_value:
            missing_fields.append("gender")
        if not fitness_goal_value:
            missing_fields.append("fitness_goal")
        if not wake_up_time:
            missing_fields.append("wake_up_time")
        if not bed_time:
            missing_fields.append("bed_time")

        if missing_fields:
            raise StorybookValidationError(
                "Missing required fields: " + ", ".join(missing_fields)
            )

        context = self._build_context(current_user=current_user)
        combined_bio = bio or self._build_bio(profile=profile, context=context)
        motivation_value = fitness_motivation or profile.fitness_goal

        storybook = Storybook(
            user_id=current_user.id,
            date=date.today(),
            status=StorybookStatus.PROCESSING,
        )
        self.storybook_repository.create(storybook=storybook, commit=True)

        try:
            payload = StorybookGenerateRequest(
                name=name_value,
                age=age_value,
                gender=gender_value,
                fitness_goal=fitness_goal_value,
                wake_up_time=wake_up_time,
                bed_time=bed_time,
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

        # TODO(storybook): honor use_reference_image to optionally reuse stored reference_image.
        selfie_bytes = await selfie.read()
        selfie_filename = selfie.filename or "selfie.png"
        selfie_content_type = selfie.content_type or "application/octet-stream"

        return StorybookGenerationJob(
            storybook_id=storybook.id,
            payload=payload,
            selfie_bytes=selfie_bytes,
            selfie_filename=selfie_filename,
            selfie_content_type=selfie_content_type,
        )

    async def process_storybook_generation(self, *, job: StorybookGenerationJob) -> None:
        storybook = self.storybook_repository.get_by_id(storybook_id=job.storybook_id)
        if storybook is None:
            return

        if storybook.status == StorybookStatus.COMPLETED:
            return

        selfie_file = StarletteUploadFile(
            filename=job.selfie_filename,
            file=BytesIO(job.selfie_bytes),
            content_type=job.selfie_content_type,
        )

        try:
            response = await self.ai_service.generate_storybook(
                payload=job.payload,
                selfie=selfie_file,
            )
        except (
            AIServiceTimeoutError,
            AIServiceConnectionError,
            AIServiceResponseError,
            AIServiceConfigError,
            AIServiceError,
        ):
            self._mark_storybook_failed(storybook=storybook)
            return

        ai_book_id = self._extract_ai_book_id(response)
        pdf_url = self._extract_pdf_url(response)
        pages = self._extract_pages(response)

        now = datetime.now(tz=timezone.utc)
        updates = {
            "status": StorybookStatus.COMPLETED,
            "generated_at": now,
            "pdf_url": pdf_url,
            "ai_book_id": ai_book_id,
        }

        with self.db.begin():
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
        image_url = self._extract_image_url(response)
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
        image_url = self._extract_image_url(response)
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

    def _build_context(self, *, current_user: User) -> StorybookContext:
        today = date.today()
        routine = self.routine_repository.get_by_user_and_date(
            user_id=current_user.id,
            routine_date=today,
        )
        routine_summary = None
        if routine is not None:
            routine_summary = (
                f"Routine {routine.date}: workout={routine.workout or 'n/a'}, "
                f"meals={routine.meals or 'n/a'}, water={routine.water_intake or 'n/a'}, "
                f"sleep={routine.sleep or 'n/a'}"
            )

        workout_plan_summary = None
        if current_user.role == UserRole.COACH:
            plans = self.workout_plan_repository.list_plans_by_coach(coach_id=current_user.id)
        else:
            plans = self.workout_plan_repository.list_plans_for_client(client_id=current_user.id)
        if plans:
            plan = plans[0]
            workout_plan_summary = f"Workout plan: {plan.title} - {plan.description or ''}"

        nutrition_plan_summary = None
        plans = self.nutrition_plan_repository.list_by_client(client_id=current_user.id)
        if plans:
            plan = plans[0]
            nutrition_plan_summary = (
                f"Nutrition plan {plan.date}: breakfast={plan.breakfast or 'n/a'}, "
                f"lunch={plan.lunch or 'n/a'}, dinner={plan.dinner or 'n/a'}"
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
