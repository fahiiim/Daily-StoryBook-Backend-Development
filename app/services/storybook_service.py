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
from app.services.weekly_summary_service import WeeklySummaryService
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
    target_date: date | None = None
    timezone: str | None = None
    mode: str | None = "PLAN"
    context_json: str | None = None


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
        target_date: date | None = None,
    ) -> StorybookGenerationJob:
        profile = self.user_repository.get_by_id(current_user.id)
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

        # Resolve target date and verify an active plan exists
        target = target_date or date.today()
        active_plan = self.nutrition_plan_repository.get_active_by_client_date(
            client_id=current_user.id,
            plan_date=target,
        )
        if active_plan is None:
            raise StorybookValidationError("No active nutrition plan for the target date")

        context = self._build_context(current_user=current_user)
        combined_bio = bio or self._build_bio(profile=profile, context=context)
        motivation_value = fitness_motivation or profile.fitness_goal

        storybook = Storybook(
            user_id=current_user.id,
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

        selfie_file = StarletteUploadFile(
            filename=job.selfie_filename,
            file=BytesIO(job.selfie_bytes),
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
                "full_name": job.payload.name if job.payload else (owner.full_name if owner else None),
                "age": (job.payload.age if job.payload else None) or (self._calculate_age(owner.date_of_birth) if owner else None),
                "gender": job.payload.gender if job.payload else (owner.gender if owner else None),
                "fitness_goal": job.payload.fitness_goal if job.payload else (owner.fitness_goal if owner else None),
                "wake_up_time": job.payload.wake_up_time if job.payload else None,
                "bed_time": job.payload.bed_time if job.payload else None,
                "short_bio": job.payload.bio if job.payload else None,
                "fitness_motivation": job.payload.fitness_motivation if job.payload else None,
            },
            "nutrition_plan": (
                {
                    "id": str(plan.id),
                    "daily_calories": plan.daily_calories,
                    "protein": plan.protein,
                    "carbs": plan.carbs,
                    "fat": plan.fat,
                    "fiber": plan.fiber,
                    "water_goal": plan.water_goal,
                    "water_unit": "ml",
                    "workout_plan": plan.workout_plan,
                    "daily_goals": plan.daily_goals,
                    "meal_targets": [],
                    "notes": plan.notes,
                    "valid_from": str(plan.date),
                    "valid_until": str(nutrition_plan_valid_until(plan.date)),
                }
                if plan
                else None
            ),
            "routine_dashboard": self._build_routine_dashboard(plan=plan, routine=routine, logs=logs),
            "workout_summary": {
                "days": [
                    {
                        "date": str(workout_day.date),
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
                "weekly_progress_percentage": aggregate.weekly_progress_percentage,
            },
            "generation": {
                "page_count": None,
                "image_style": (job.payload.image_style if job.payload else None) or "premium_wellness",
            },
        }
        return json.dumps(context, default=str)

    def _workout_repo_for_context(self) -> WorkoutPlanCompletionRepository:
        # Reuse existing session-bound repository
        return WorkoutPlanCompletionRepository(self.db)

    def _goal_repo_for_context(self) -> DailyGoalCompletionRepository:
        return DailyGoalCompletionRepository(self.db)

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
            "kcal": (float(plan.daily_calories) - totals["kcal"]) if plan and plan.daily_calories is not None else None,
            "protein": (float(plan.protein) - totals["protein"]) if plan and plan.protein is not None else None,
            "carbs": (float(plan.carbs) - totals["carbs"]) if plan and plan.carbs is not None else None,
            "fat": (float(plan.fat) - totals["fat"]) if plan and plan.fat is not None else None,
            "fiber": (float(plan.fiber) - totals["fiber"]) if plan and plan.fiber is not None else None,
            "water": (float(plan.water_goal) - totals["water"]) if plan and plan.water_goal is not None else None,
        }
        return {
            "date": str(routine.date if routine else (plan.date if plan else date.today())),
            "routine": (
                {
                    "id": str(routine.id),
                    "water_intake": totals["water"],
                    "sleep": routine.sleep,
                    "completion_status": routine.completion_status,
                }
                if routine
                else None
            ),
            "totals": totals,
            "remaining": remaining,
            "logged_meals": [
                {
                    "id": str(log.id),
                    "meal_type": getattr(log, "meal_type", None),
                    "food_name": getattr(log, "food_name", None),
                    "amount": getattr(log, "amount", None),
                    "amount_unit": getattr(log, "amount_unit", None),
                    "kcal": getattr(log, "kcal", None),
                    "protein": getattr(log, "protein", None),
                    "carbs": getattr(log, "carbs", None),
                    "fat": getattr(log, "fat", None),
                    "fiber": getattr(log, "fiber", None),
                    "logged_at": getattr(log, "logged_at", None),
                }
                for log in (logs or [])
            ],
        }

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
        nutrition_plan_summary = None
        plan = self.nutrition_plan_repository.get_active_by_client_date(
            client_id=current_user.id,
            plan_date=today,
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
