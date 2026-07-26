from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid5

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.daily_goal import DailyGoalCompletion
from app.models.nutrition_plan import NutritionPlan, nutrition_plan_valid_until
from app.models.routine import Routine
from app.models.user import User, UserRole
from app.models.weekly_summary import WeeklySummary
from app.models.workout_plan import WorkoutPlanCompletionEvent
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.daily_goal_repository import DailyGoalCompletionRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.storybook_repository import StorybookRepository
from app.repositories.user_repository import UserRepository
from app.repositories.weekly_summary_repository import WeeklySummaryRepository
from app.repositories.workout_plan_repository import WorkoutPlanCompletionRepository
from app.schemas.ai import WeeklySummaryGenerateRequest
from app.schemas.weekly_summary import (
    DailyGoalItemRead,
    DailyGoalsTodayRead,
    DailyProgressPoint,
    WeeklyProgressAnalyticsRead,
    WeeklyProgressAverages,
    WeeklyProgressCoverage,
)
from app.services.workout_plan_service import build_workout_item_id
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


class DailyGoalNotFoundError(WeeklySummaryServiceError):
    pass


DAILY_GOAL_ITEM_NAMESPACE = UUID("a6824ffb-ad9d-49df-9f50-c6ce38a75bca")


def build_daily_goal_item_id(
    *,
    nutrition_plan_id: UUID,
    position: int,
    instruction: str,
) -> UUID:
    return uuid5(DAILY_GOAL_ITEM_NAMESPACE, f"{nutrition_plan_id}:{position}:{instruction}")


class WeeklySummaryService:
    def __init__(
        self,
        *,
        db: Session,
        ai_service: AIService,
        weekly_summary_repository: WeeklySummaryRepository,
        routine_repository: RoutineRepository,
        workout_plan_repository: WorkoutPlanCompletionRepository,
        daily_goal_repository: DailyGoalCompletionRepository,
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
        self.daily_goal_repository = daily_goal_repository
        self.nutrition_plan_repository = nutrition_plan_repository
        self.storybook_repository = storybook_repository
        self.user_repository = user_repository
        self.coach_client_repository = coach_client_repository

    def get_current_week_analytics(
        self,
        *,
        current_user: User,
        user_id: UUID | None = None,
        as_of_date: date | None = None,
    ) -> WeeklyProgressAnalyticsRead:
        target_user = self._resolve_target_user(current_user=current_user, user_id=user_id)
        effective_today = as_of_date or date.today()
        week_start, week_end = self._get_week_range(effective_today)
        routines = {
            routine.date: routine
            for routine in self.routine_repository.list_by_user_between_dates(
                user_id=target_user.id,
                start_date=week_start,
                end_date=week_end,
            )
        }
        workout_events = self.workout_plan_repository.list_events_for_client_through_date(
            client_id=target_user.id,
            end_date=week_end,
        )
        goal_completions = self.daily_goal_repository.list_by_client_between_dates(
            client_id=target_user.id,
            start_date=week_start,
            end_date=week_end,
        )

        points: list[DailyProgressPoint] = []
        for offset in range(7):
            point_date = week_start + timedelta(days=offset)
            if point_date > effective_today:
                points.append(
                    DailyProgressPoint(
                        date=point_date,
                        day=point_date.strftime("%a").upper(),
                        workout_score=None,
                        meal_score=None,
                        daily_goal_score=None,
                        combined_score=None,
                        is_future=True,
                    )
                )
                continue

            plan = self.nutrition_plan_repository.get_active_by_client_date(
                client_id=target_user.id,
                plan_date=point_date,
            )
            routine = routines.get(point_date)
            meal_score, meal_components = self._calculate_meal_score(plan=plan, routine=routine)
            workout_score, workout_completed, workout_assigned = self._calculate_workout_score(
                plan=plan,
                point_date=point_date,
                events=workout_events,
            )
            goal_score, goals_completed, goals_assigned = self._calculate_daily_goal_score(
                plan=plan,
                point_date=point_date,
                completions=goal_completions,
            )
            available_scores = [
                score
                for score in (workout_score, meal_score, goal_score)
                if score is not None
            ]
            combined_score = (
                round(sum(available_scores) / len(available_scores), 2)
                if available_scores
                else None
            )
            points.append(
                DailyProgressPoint(
                    date=point_date,
                    day=point_date.strftime("%a").upper(),
                    workout_score=workout_score,
                    meal_score=meal_score,
                    daily_goal_score=goal_score,
                    combined_score=combined_score,
                    workout_completed=workout_completed,
                    workout_assigned=workout_assigned,
                    meal_components_scored=meal_components,
                    daily_goals_completed=goals_completed,
                    daily_goals_assigned=goals_assigned,
                    workout_applicable=workout_score is not None,
                    meal_applicable=meal_score is not None,
                    daily_goal_applicable=goal_score is not None,
                )
            )

        elapsed_points = [point for point in points if not point.is_future]
        workout_average = self._average_score(elapsed_points, "workout_score")
        meal_average = self._average_score(elapsed_points, "meal_score")
        goal_average = self._average_score(elapsed_points, "daily_goal_score")
        combined_average = self._average_score(elapsed_points, "combined_score")
        ending_workout_rate = next(
            (
                point.workout_score
                for point in reversed(elapsed_points)
                if point.workout_score is not None
            ),
            None,
        )
        combined_days = sum(point.combined_score is not None for point in elapsed_points)
        return WeeklyProgressAnalyticsRead(
            user_id=target_user.id,
            week_start=week_start,
            week_end=week_end,
            as_of_date=effective_today,
            as_of=datetime.now(tz=timezone.utc),
            is_partial_week=effective_today < week_end,
            daily_points=points,
            weekly_averages=WeeklyProgressAverages(
                workout_score=workout_average,
                meal_score=meal_average,
                daily_goal_score=goal_average,
                combined_score=combined_average,
                ending_workout_completion_rate=ending_workout_rate,
            ),
            coverage=WeeklyProgressCoverage(
                elapsed_days=len(elapsed_points),
                workout_days_scored=sum(point.workout_score is not None for point in elapsed_points),
                meal_days_scored=sum(point.meal_score is not None for point in elapsed_points),
                daily_goal_days_scored=sum(
                    point.daily_goal_score is not None for point in elapsed_points
                ),
                combined_days_scored=combined_days,
                complete=effective_today >= week_end and combined_days == len(elapsed_points),
            ),
        )

    def get_today_daily_goals(
        self,
        *,
        current_user: User,
        target_date: date | None = None,
    ) -> DailyGoalsTodayRead:
        if current_user.role != UserRole.SELF:
            raise WeeklySummaryAccessError("SELF role required")
        goal_date = target_date or date.today()
        plan = self.nutrition_plan_repository.get_active_by_client_date(
            client_id=current_user.id,
            plan_date=goal_date,
        )
        if plan is None:
            raise WeeklySummaryNotFoundError("No active daily goals assigned")
        completions = self.daily_goal_repository.list_by_plan_client_date(
            nutrition_plan_id=plan.id,
            client_id=current_user.id,
            goal_date=goal_date,
        )
        completion_by_item = {completion.goal_item_id: completion for completion in completions}
        items: list[DailyGoalItemRead] = []
        for position, instruction in enumerate(plan.daily_goals):
            item_id = build_daily_goal_item_id(
                nutrition_plan_id=plan.id,
                position=position,
                instruction=instruction,
            )
            completion = completion_by_item.get(item_id)
            items.append(
                DailyGoalItemRead(
                    id=item_id,
                    position=position,
                    instruction=instruction,
                    completed=bool(completion and completion.is_completed),
                    completed_at=(
                        completion.completed_at
                        if completion is not None and completion.is_completed
                        else None
                    ),
                )
            )
        completed_count = sum(item.completed for item in items)
        total_count = len(items)
        return DailyGoalsTodayRead(
            nutrition_plan_id=plan.id,
            goal_date=goal_date,
            items=items,
            completed_count=completed_count,
            total_count=total_count,
            completion_rate=(
                round((completed_count / total_count) * 100, 2) if total_count else 0.0
            ),
            all_completed=total_count > 0 and completed_count == total_count,
        )

    def update_today_daily_goal(
        self,
        *,
        current_user: User,
        goal_item_id: UUID,
        completed: bool,
        target_date: date | None = None,
    ) -> DailyGoalItemRead:
        goal_date = target_date or date.today()
        goals = self.get_today_daily_goals(current_user=current_user, target_date=goal_date)
        item = next((candidate for candidate in goals.items if candidate.id == goal_item_id), None)
        if item is None:
            raise DailyGoalNotFoundError("Assigned daily goal not found")
        completed_at = datetime.now(tz=timezone.utc) if completed else None
        completion = self.daily_goal_repository.set_completion(
            nutrition_plan_id=goals.nutrition_plan_id,
            client_id=current_user.id,
            goal_item_id=goal_item_id,
            goal_date=goal_date,
            completed=completed,
            completed_at=completed_at,
        )
        return item.model_copy(
            update={
                "completed": completion.is_completed,
                "completed_at": completion.completed_at,
            }
        )

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
                        "title": f"Assigned workout plan starting {plan.date}",
                        "description": plan.notes,
                        "exercises": "; ".join(plan.workout_plan),
                        "is_active": plan.date <= date.today() <= nutrition_plan_valid_until(plan.date),
                    }
                    for plan in nutrition_plans
                    if plan.workout_plan
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

        try:
            self.weekly_summary_repository.create(summary=weekly_summary, commit=False)
            self.db.commit()
            self.db.refresh(weekly_summary)
        except Exception:
            self.db.rollback()
            raise

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

        if not self.coach_client_repository.accepted_relationship_exists(
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
    def _calculate_meal_score(
        *,
        plan: NutritionPlan | None,
        routine: Routine | None,
    ) -> tuple[float | None, int]:
        if plan is None:
            return None, 0
        target_actual_pairs = [
            (plan.daily_calories, routine.meals_kcal if routine is not None else 0.0),
            (plan.protein, routine.intake_protein if routine is not None else 0.0),
            (plan.carbs, routine.intake_carbs if routine is not None else 0.0),
            (plan.fat, routine.intake_fats if routine is not None else 0.0),
            (plan.fiber, routine.intake_fiber if routine is not None else 0.0),
        ]
        configured = [(target, actual or 0.0) for target, actual in target_actual_pairs if target is not None]
        if not configured:
            return None, 0

        ratios: list[float] = []
        for target, actual in configured:
            target_value = float(target)
            actual_value = max(float(actual), 0.0)
            if target_value == 0:
                ratios.append(1.0 if actual_value == 0 else 0.0)
            else:
                ratios.append(min(actual_value / target_value, 1.0))
        return round((sum(ratios) / len(ratios)) * 100, 2), len(ratios)

    @staticmethod
    def _calculate_workout_score(
        *,
        plan: NutritionPlan | None,
        point_date: date,
        events: list[WorkoutPlanCompletionEvent],
    ) -> tuple[float | None, int, int]:
        if plan is None or not plan.workout_plan:
            return None, 0, 0
        item_ids = {
            build_workout_item_id(
                nutrition_plan_id=plan.id,
                position=position,
                instruction=instruction,
            )
            for position, instruction in enumerate(plan.workout_plan)
        }
        latest_state: dict[UUID, bool] = {}
        for event in events:
            if (
                event.nutrition_plan_id == plan.id
                and event.workout_item_id in item_ids
                and event.effective_date <= point_date
            ):
                latest_state[event.workout_item_id] = event.completed
        completed_count = sum(latest_state.get(item_id, False) for item_id in item_ids)
        total_count = len(item_ids)
        return round((completed_count / total_count) * 100, 2), completed_count, total_count

    @staticmethod
    def _calculate_daily_goal_score(
        *,
        plan: NutritionPlan | None,
        point_date: date,
        completions: list[DailyGoalCompletion],
    ) -> tuple[float | None, int, int]:
        if plan is None or not plan.daily_goals:
            return None, 0, 0
        item_ids = {
            build_daily_goal_item_id(
                nutrition_plan_id=plan.id,
                position=position,
                instruction=instruction,
            )
            for position, instruction in enumerate(plan.daily_goals)
        }
        completed_ids = {
            completion.goal_item_id
            for completion in completions
            if completion.nutrition_plan_id == plan.id
            and completion.goal_date == point_date
            and completion.goal_item_id in item_ids
            and completion.is_completed
        }
        completed_count = len(completed_ids)
        total_count = len(item_ids)
        return round((completed_count / total_count) * 100, 2), completed_count, total_count

    @staticmethod
    def _average_score(points: list[DailyProgressPoint], field_name: str) -> float | None:
        values = [
            value
            for point in points
            if (value := getattr(point, field_name)) is not None
        ]
        return round(sum(values) / len(values), 2) if values else None

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