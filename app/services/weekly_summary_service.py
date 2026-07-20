from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.weekly_summary import WeeklySummary
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.storybook_repository import StorybookRepository
from app.repositories.user_repository import UserRepository
from app.repositories.weekly_summary_repository import WeeklySummaryRepository
from app.repositories.workout_plan_repository import WorkoutPlanRepository
from app.schemas.ai import WeeklySummaryGenerateRequest
from app.services.ai_service import (
    AIService,
    AIServiceConfigError,
    AIServiceConnectionError,
    AIServiceError,
    AIServiceResponseError,
    AIServiceTimeoutError,
)


class WeeklySummaryServiceError(Exception):
    pass


class WeeklySummaryNotFoundError(WeeklySummaryServiceError):
    pass


class WeeklySummaryAccessError(WeeklySummaryServiceError):
    pass


class WeeklySummaryValidationError(WeeklySummaryServiceError):
    pass


class WeeklySummaryService:
    def __init__(
        self,
        *,
        db: Session,
        ai_service: AIService,
        weekly_summary_repository: WeeklySummaryRepository,
        routine_repository: RoutineRepository,
        workout_plan_repository: WorkoutPlanRepository,
        nutrition_plan_repository: NutritionPlanRepository,
        storybook_repository: StorybookRepository,
        user_repository: UserRepository,
        coach_client_repository: CoachClientRepository,
    ) -> None:
        self.db = db
        self.ai_service = ai_service
        self.weekly_summary_repository = weekly_summary_repository
        self.routine_repository = routine_repository
        self.workout_plan_repository = workout_plan_repository
        self.nutrition_plan_repository = nutrition_plan_repository
        self.storybook_repository = storybook_repository
        self.user_repository = user_repository
        self.coach_client_repository = coach_client_repository

    async def generate_weekly_summary(
        self,
        *,
        current_user: User,
        user_id: UUID | None = None,
    ) -> WeeklySummary:
        target_user = self._resolve_target_user(current_user=current_user, user_id=user_id)
        week_start, week_end = self._get_week_range(date.today())

        existing = self.weekly_summary_repository.get_by_user_and_week_start(
            user_id=target_user.id,
            week_start=week_start,
        )
        if existing is not None:
            return existing

        routines = self.routine_repository.list_by_user_between_dates(
            user_id=target_user.id,
            start_date=week_start,
            end_date=week_end,
        )
        workout_plans = (
            self.workout_plan_repository.list_plans_by_coach(coach_id=target_user.id)
            if target_user.role == UserRole.COACH
            else self.workout_plan_repository.list_plans_for_client(client_id=target_user.id)
        )
        nutrition_plans = self.nutrition_plan_repository.list_by_client(client_id=target_user.id)
        storybooks = self.storybook_repository.list_by_user_between_dates(
            user_id=target_user.id,
            start_date=week_start,
            end_date=week_end,
        )

        completed_tasks = {
            "completed_routines": sum(1 for routine in routines if routine.completion_status),
            "total_routines": len(routines),
            "completed_storybooks": sum(1 for book in storybooks if book.status.name == "COMPLETED"),
        }

        try:
            payload = WeeklySummaryGenerateRequest(
                week_start=str(week_start),
                week_end=str(week_end),
                profile={
                    "full_name": target_user.full_name,
                    "email": target_user.email,
                    "age": target_user.age,
                    "gender": target_user.gender,
                    "occupation": target_user.occupation,
                    "fitness_goal": target_user.fitness_goal,
                },
                routine_entries=[
                    {
                        "date": str(routine.date),
                        "workout": routine.workout,
                        "meals": routine.meals,
                        "water_intake": routine.water_intake,
                        "sleep": routine.sleep,
                        "notes": routine.notes,
                        "completion_status": routine.completion_status,
                    }
                    for routine in routines
                ],
                workout_plans=[
                    {
                        "title": plan.title,
                        "description": plan.description,
                        "exercises": plan.exercises,
                        "is_active": plan.is_active,
                    }
                    for plan in workout_plans
                ],
                nutrition_plans=[
                    {
                        "date": str(plan.date),
                        "daily_calories": plan.daily_calories,
                        "protein": plan.protein,
                        "carbs": plan.carbs,
                        "fat": plan.fat,
                        "fiber": plan.fiber,
                        "water_goal": plan.water_goal,
                        "workout_plan": plan.workout_plan,
                        "daily_goals": plan.daily_goals,
                        "notes": plan.notes,
                    }
                    for plan in nutrition_plans
                ],
                storybooks=[
                    {
                        "date": str(book.date),
                        "status": book.status.value,
                        "pdf_url": book.pdf_url,
                    }
                    for book in storybooks
                ],
                completed_tasks=completed_tasks,
            )
        except ValidationError as exc:
            raise WeeklySummaryValidationError(str(exc)) from exc

        response = await self.ai_service.generate_weekly_summary(payload=payload)
        summary_text = self._extract_summary(response)
        image_url = self._extract_image_url(response)

        if not summary_text:
            raise WeeklySummaryServiceError("AI response missing summary")

        generated_at = datetime.now(tz=timezone.utc)
        weekly_summary = WeeklySummary(
            user_id=target_user.id,
            week_start=week_start,
            week_end=week_end,
            summary=summary_text,
            image_url=image_url,
            generated_at=generated_at,
        )

        with self.db.begin():
            self.weekly_summary_repository.create(summary=weekly_summary, commit=False)

        return weekly_summary

    def get_current_summary(
        self,
        *,
        current_user: User,
        user_id: UUID | None = None,
    ) -> WeeklySummary:
        target_user = self._resolve_target_user(current_user=current_user, user_id=user_id)
        week_start, _ = self._get_week_range(date.today())
        summary = self.weekly_summary_repository.get_by_user_and_week_start(
            user_id=target_user.id,
            week_start=week_start,
        )
        if summary is None:
            raise WeeklySummaryNotFoundError("Weekly summary not found")
        return summary

    def get_history(
        self,
        *,
        current_user: User,
        user_id: UUID | None = None,
    ) -> list[WeeklySummary]:
        target_user = self._resolve_target_user(current_user=current_user, user_id=user_id)
        return self.weekly_summary_repository.list_by_user(user_id=target_user.id)

    def _resolve_target_user(self, *, current_user: User, user_id: UUID | None) -> User:
        if user_id is None or user_id == current_user.id:
            return current_user

        target_user = self.user_repository.get_by_id(user_id)
        if target_user is None:
            raise WeeklySummaryNotFoundError("User not found")

        if current_user.role == UserRole.ADMIN:
            return target_user

        if current_user.role != UserRole.COACH:
            raise WeeklySummaryAccessError("Access to weekly summary is forbidden")

        if not self.coach_client_repository.relationship_exists(
            coach_id=current_user.id,
            client_id=target_user.id,
        ):
            raise WeeklySummaryAccessError("Access to weekly summary is forbidden")

        return target_user

    @staticmethod
    def _get_week_range(today: date) -> tuple[date, date]:
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        return week_start, week_end

    @staticmethod
    def _extract_summary(response: dict[str, object]) -> str | None:
        value = response.get("summary")
        if isinstance(value, str):
            return value
        nested = response.get("weekly_summary")
        if isinstance(nested, dict):
            nested_value = nested.get("summary")
            if isinstance(nested_value, str):
                return nested_value
        return None

    @staticmethod
    def _extract_image_url(response: dict[str, object]) -> str | None:
        value = response.get("image_url")
        if isinstance(value, str):
            return value
        nested = response.get("weekly_summary")
        if isinstance(nested, dict):
            nested_value = nested.get("image_url")
            if isinstance(nested_value, str):
                return nested_value
        return None


__all__ = [
    "AIServiceConfigError",
    "AIServiceConnectionError",
    "AIServiceError",
    "AIServiceResponseError",
    "AIServiceTimeoutError",
    "WeeklySummaryAccessError",
    "WeeklySummaryNotFoundError",
    "WeeklySummaryService",
    "WeeklySummaryServiceError",
    "WeeklySummaryValidationError",
]