from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid5

from app.models.daily_goal import DailyGoalCompletion
from app.models.nutrition_plan import NutritionPlan
from app.models.routine import Routine
from app.models.user import User
from app.models.workout_plan import WorkoutPlanCompletionEvent
from app.repositories.daily_goal_repository import DailyGoalCompletionRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.workout_plan_repository import WorkoutPlanCompletionRepository
from app.schemas.weekly_summary import (
    DailyProgressPoint,
    WeeklyProgressAnalyticsRead,
    WeeklyProgressAverages,
    WeeklyProgressCoverage,
)
from app.services.workout_plan_service import build_workout_item_id


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
        routine_repository: RoutineRepository,
        workout_plan_repository: WorkoutPlanCompletionRepository,
        daily_goal_repository: DailyGoalCompletionRepository,
        nutrition_plan_repository: NutritionPlanRepository,
    ) -> None:
        self.routine_repository = routine_repository
        self.workout_plan_repository = workout_plan_repository
        self.daily_goal_repository = daily_goal_repository
        self.nutrition_plan_repository = nutrition_plan_repository

    def get_current_week_analytics(
        self,
        *,
        current_user: User,
        as_of_date: date | None = None,
    ) -> WeeklyProgressAnalyticsRead:
        effective_today = as_of_date or date.today()
        week_start, week_end = self._get_week_range(effective_today)
        routines = {
            routine.date: routine
            for routine in self.routine_repository.list_by_user_between_dates(
                user_id=current_user.id,
                start_date=week_start,
                end_date=week_end,
            )
        }
        workout_events = self.workout_plan_repository.list_events_for_client_through_date(
            client_id=current_user.id,
            end_date=week_end,
        )
        goal_completions = self.daily_goal_repository.list_by_client_between_dates(
            client_id=current_user.id,
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
                client_id=current_user.id,
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
                score for score in (workout_score, meal_score, goal_score) if score is not None
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
            user_id=current_user.id,
            week_start=week_start,
            week_end=week_end,
            as_of_date=effective_today,
            as_of=datetime.now(tz=timezone.utc),
            is_partial_week=effective_today < week_end,
            daily_points=points,
            weekly_averages=WeeklyProgressAverages(
                workout_score=self._average_score(elapsed_points, "workout_score"),
                meal_score=self._average_score(elapsed_points, "meal_score"),
                daily_goal_score=self._average_score(elapsed_points, "daily_goal_score"),
                combined_score=self._average_score(elapsed_points, "combined_score"),
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

    @staticmethod
    def _get_week_range(today: date) -> tuple[date, date]:
        week_start = today - timedelta(days=today.weekday())
        return week_start, week_start + timedelta(days=6)

    @staticmethod
    def _calculate_meal_score(
        *,
        plan: NutritionPlan | None,
        routine: Routine | None,
    ) -> tuple[float | None, int]:
        if plan is None:
            return None, 0
        pairs = [
            (plan.daily_calories, routine.meals_kcal if routine is not None else 0.0),
            (plan.protein, routine.intake_protein if routine is not None else 0.0),
            (plan.carbs, routine.intake_carbs if routine is not None else 0.0),
            (plan.fat, routine.intake_fats if routine is not None else 0.0),
            (plan.fiber, routine.intake_fiber if routine is not None else 0.0),
        ]
        configured = [(target, actual or 0.0) for target, actual in pairs if target is not None]
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
            value for point in points if (value := getattr(point, field_name)) is not None
        ]
        return round(sum(values) / len(values), 2) if values else None
