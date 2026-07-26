from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid5

from app.models.daily_goal import DailyGoalCompletion
from app.models.nutrition_plan import NutritionPlan, nutrition_plan_valid_until
from app.models.routine import Routine
from app.models.routine_macro_log import RoutineMacroLog
from app.models.user import User, UserRole
from app.models.workout_plan import WorkoutPlanCompletionEvent
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.daily_goal_repository import DailyGoalCompletionRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_macro_log_repository import RoutineMacroLogRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_plan_repository import WorkoutPlanCompletionRepository
from app.schemas.weekly_summary import (
    DailyProgressPoint,
    WeeklyGoalDayRead,
    WeeklyGoalItemRead,
    WeeklyGoalsRead,
    WeeklyMealComponentRead,
    WeeklyMealDayRead,
    WeeklyMealLogRead,
    WeeklyMealRemainingRead,
    WeeklyMealsRead,
    WeeklyMealTargetsRead,
    WeeklyMealTotalsRead,
    WeeklyPlanRefRead,
    WeeklyProgressAnalyticsRead,
    WeeklyProgressAverages,
    WeeklyProgressCoverage,
    WeeklyWorkoutDayRead,
    WeeklyWorkoutItemRead,
    WeeklyWorkoutsRead,
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


class WeeklySummaryClientNotFoundError(Exception):
    pass


class WeeklySummaryClientNotManagedError(Exception):
    pass


@dataclass(frozen=True)
class _WeekContext:
    user_id: UUID
    week_start: date
    week_end: date
    as_of_date: date
    as_of: datetime
    plans: dict[date, NutritionPlan | None]
    routines: dict[date, Routine]
    meal_logs: dict[UUID, list[RoutineMacroLog]]
    workout_events: list[WorkoutPlanCompletionEvent]
    goal_completions: list[DailyGoalCompletion]


class WeeklySummaryService:
    def __init__(
        self,
        *,
        routine_repository: RoutineRepository,
        routine_macro_log_repository: RoutineMacroLogRepository,
        workout_plan_repository: WorkoutPlanCompletionRepository,
        daily_goal_repository: DailyGoalCompletionRepository,
        nutrition_plan_repository: NutritionPlanRepository,
        user_repository: UserRepository,
        coach_client_repository: CoachClientRepository,
    ) -> None:
        self.routine_repository = routine_repository
        self.routine_macro_log_repository = routine_macro_log_repository
        self.workout_plan_repository = workout_plan_repository
        self.daily_goal_repository = daily_goal_repository
        self.nutrition_plan_repository = nutrition_plan_repository
        self.user_repository = user_repository
        self.coach_client_repository = coach_client_repository

    def get_current_week_analytics(
        self,
        *,
        current_user: User,
        as_of_date: date | None = None,
    ) -> WeeklyProgressAnalyticsRead:
        context = self._build_context(user_id=current_user.id, as_of_date=as_of_date)
        return self._build_analytics(context)

    def get_current_week_workouts(
        self,
        *,
        current_user: User,
        as_of_date: date | None = None,
    ) -> WeeklyWorkoutsRead:
        return self._build_workouts(
            self._build_context(user_id=current_user.id, as_of_date=as_of_date)
        )

    def get_current_week_meals(
        self,
        *,
        current_user: User,
        as_of_date: date | None = None,
    ) -> WeeklyMealsRead:
        return self._build_meals(
            self._build_context(user_id=current_user.id, as_of_date=as_of_date)
        )

    def get_current_week_goals(
        self,
        *,
        current_user: User,
        as_of_date: date | None = None,
    ) -> WeeklyGoalsRead:
        return self._build_goals(
            self._build_context(user_id=current_user.id, as_of_date=as_of_date)
        )

    def get_client_current_week_analytics(
        self,
        *,
        current_coach: User,
        client_id: UUID,
        as_of_date: date | None = None,
    ) -> WeeklyProgressAnalyticsRead:
        self._ensure_managed_client(current_coach=current_coach, client_id=client_id)
        return self._build_analytics(self._build_context(user_id=client_id, as_of_date=as_of_date))

    def get_client_current_week_workouts(
        self,
        *,
        current_coach: User,
        client_id: UUID,
        as_of_date: date | None = None,
    ) -> WeeklyWorkoutsRead:
        self._ensure_managed_client(current_coach=current_coach, client_id=client_id)
        return self._build_workouts(self._build_context(user_id=client_id, as_of_date=as_of_date))

    def get_client_current_week_meals(
        self,
        *,
        current_coach: User,
        client_id: UUID,
        as_of_date: date | None = None,
    ) -> WeeklyMealsRead:
        self._ensure_managed_client(current_coach=current_coach, client_id=client_id)
        return self._build_meals(self._build_context(user_id=client_id, as_of_date=as_of_date))

    def get_client_current_week_goals(
        self,
        *,
        current_coach: User,
        client_id: UUID,
        as_of_date: date | None = None,
    ) -> WeeklyGoalsRead:
        self._ensure_managed_client(current_coach=current_coach, client_id=client_id)
        return self._build_goals(self._build_context(user_id=client_id, as_of_date=as_of_date))

    def _build_context(self, *, user_id: UUID, as_of_date: date | None) -> _WeekContext:
        effective_today = as_of_date or date.today()
        week_start, week_end = self._get_week_range(effective_today)
        routines = {
            routine.date: routine
            for routine in self.routine_repository.list_by_user_between_dates(
                user_id=user_id,
                start_date=week_start,
                end_date=week_end,
            )
        }
        meal_logs = {
            routine.id: self.routine_macro_log_repository.list_by_routine_for_user(
                routine_id=routine.id,
                user_id=user_id,
            )
            for routine in routines.values()
        }
        plans = {
            week_start + timedelta(days=offset): self.nutrition_plan_repository.get_active_by_client_date(
                client_id=user_id,
                plan_date=week_start + timedelta(days=offset),
            )
            for offset in range(7)
        }
        return _WeekContext(
            user_id=user_id,
            week_start=week_start,
            week_end=week_end,
            as_of_date=effective_today,
            as_of=datetime.now(tz=timezone.utc),
            plans=plans,
            routines=routines,
            meal_logs=meal_logs,
            workout_events=self.workout_plan_repository.list_events_for_client_through_date(
                client_id=user_id,
                end_date=week_end,
            ),
            goal_completions=self.daily_goal_repository.list_by_client_between_dates(
                client_id=user_id,
                start_date=week_start,
                end_date=week_end,
            ),
        )

    def _build_analytics(self, context: _WeekContext) -> WeeklyProgressAnalyticsRead:
        workout_days = self._build_workouts(context).days
        meal_days = self._build_meals(context).days
        goal_days = self._build_goals(context).days
        points: list[DailyProgressPoint] = []
        for workout, meal, goal in zip(workout_days, meal_days, goal_days, strict=True):
            scores = [
                score
                for score in (workout.workout_score, meal.meal_score, goal.daily_goal_score)
                if score is not None
            ]
            points.append(
                DailyProgressPoint(
                    date=workout.date,
                    day=workout.day,
                    workout_score=workout.workout_score,
                    meal_score=meal.meal_score,
                    daily_goal_score=goal.daily_goal_score,
                    combined_score=round(sum(scores) / len(scores), 2) if scores else None,
                    workout_completed=workout.completed_count,
                    workout_assigned=workout.assigned_count,
                    meal_components_scored=meal.components_scored,
                    daily_goals_completed=goal.completed_count,
                    daily_goals_assigned=goal.assigned_count,
                    workout_applicable=workout.applicable,
                    meal_applicable=meal.applicable,
                    daily_goal_applicable=goal.applicable,
                    is_future=workout.is_future,
                )
            )
        elapsed = [point for point in points if not point.is_future]
        ending_workout = next(
            (point.workout_score for point in reversed(elapsed) if point.workout_score is not None),
            None,
        )
        combined_days = sum(point.combined_score is not None for point in elapsed)
        return WeeklyProgressAnalyticsRead(
            user_id=context.user_id,
            week_start=context.week_start,
            week_end=context.week_end,
            as_of_date=context.as_of_date,
            as_of=context.as_of,
            is_partial_week=context.as_of_date < context.week_end,
            daily_points=points,
            weekly_averages=WeeklyProgressAverages(
                workout_score=self._average_score(elapsed, "workout_score"),
                meal_score=self._average_score(elapsed, "meal_score"),
                daily_goal_score=self._average_score(elapsed, "daily_goal_score"),
                combined_score=self._average_score(elapsed, "combined_score"),
                ending_workout_completion_rate=ending_workout,
            ),
            coverage=WeeklyProgressCoverage(
                elapsed_days=len(elapsed),
                workout_days_scored=sum(point.workout_score is not None for point in elapsed),
                meal_days_scored=sum(point.meal_score is not None for point in elapsed),
                daily_goal_days_scored=sum(point.daily_goal_score is not None for point in elapsed),
                combined_days_scored=combined_days,
                complete=context.as_of_date >= context.week_end and combined_days == len(elapsed),
            ),
        )

    def _build_workouts(self, context: _WeekContext) -> WeeklyWorkoutsRead:
        days: list[WeeklyWorkoutDayRead] = []
        for point_date in self._week_dates(context):
            if point_date > context.as_of_date:
                days.append(self._future_workout_day(point_date))
                continue
            plan = context.plans[point_date]
            if plan is None or not plan.workout_plan:
                days.append(
                    WeeklyWorkoutDayRead(
                        date=point_date,
                        day=self._day_code(point_date),
                        is_future=False,
                        applicable=False,
                        plan=self._plan_ref(plan),
                        workout_score=None,
                        completed_count=0,
                        assigned_count=0,
                        all_completed=None,
                    )
                )
                continue
            items: list[WeeklyWorkoutItemRead] = []
            for position, instruction in enumerate(plan.workout_plan):
                item_id = build_workout_item_id(
                    nutrition_plan_id=plan.id,
                    position=position,
                    instruction=instruction,
                )
                event = self._latest_workout_event(
                    plan_id=plan.id,
                    item_id=item_id,
                    point_date=point_date,
                    events=context.workout_events,
                )
                items.append(
                    WeeklyWorkoutItemRead(
                        id=item_id,
                        position=position,
                        instruction=instruction,
                        completed=bool(event and event.completed),
                        state_effective_date=event.effective_date if event else None,
                        state_changed_at=event.occurred_at if event else None,
                    )
                )
            completed_count = sum(item.completed for item in items)
            total_count = len(items)
            days.append(
                WeeklyWorkoutDayRead(
                    date=point_date,
                    day=self._day_code(point_date),
                    is_future=False,
                    applicable=True,
                    plan=self._plan_ref(plan),
                    workout_score=round((completed_count / total_count) * 100, 2),
                    completed_count=completed_count,
                    assigned_count=total_count,
                    all_completed=completed_count == total_count,
                    items=items,
                )
            )
        return WeeklyWorkoutsRead(**self._detail_base(context), days=days)

    def _build_meals(self, context: _WeekContext) -> WeeklyMealsRead:
        days: list[WeeklyMealDayRead] = []
        for point_date in self._week_dates(context):
            if point_date > context.as_of_date:
                days.append(self._future_meal_day(point_date))
                continue
            plan = context.plans[point_date]
            routine = context.routines.get(point_date)
            logs = context.meal_logs.get(routine.id, []) if routine else []
            consumed = WeeklyMealTotalsRead(
                kcal=round(routine.meals_kcal or 0.0, 2) if routine else 0.0,
                protein=round(routine.intake_protein or 0.0, 2) if routine else 0.0,
                carbs=round(routine.intake_carbs or 0.0, 2) if routine else 0.0,
                fat=round(routine.intake_fats or 0.0, 2) if routine else 0.0,
                fiber=round(routine.intake_fiber or 0.0, 2) if routine else 0.0,
                water=round(routine.water_intake or 0.0, 2) if routine else 0.0,
            )
            targets = WeeklyMealTargetsRead(
                kcal=float(plan.daily_calories) if plan and plan.daily_calories is not None else None,
                protein=float(plan.protein) if plan and plan.protein is not None else None,
                carbs=float(plan.carbs) if plan and plan.carbs is not None else None,
                fat=float(plan.fat) if plan and plan.fat is not None else None,
                fiber=float(plan.fiber) if plan and plan.fiber is not None else None,
                water=float(plan.water_goal) if plan and plan.water_goal is not None else None,
            )
            components = self._meal_components(targets=targets, consumed=consumed)
            meal_score = (
                round(sum(item.attainment_percent for item in components) / len(components), 2)
                if components
                else None
            )
            days.append(
                WeeklyMealDayRead(
                    date=point_date,
                    day=self._day_code(point_date),
                    is_future=False,
                    applicable=bool(components),
                    plan=self._plan_ref(plan),
                    routine_id=routine.id if routine else None,
                    meal_score=meal_score,
                    components_scored=len(components),
                    components_met=sum(item.met for item in components),
                    completed=all(item.met for item in components) if components else None,
                    targets=targets,
                    consumed=consumed,
                    remaining=WeeklyMealRemainingRead(
                        kcal=self._remaining(targets.kcal, consumed.kcal),
                        protein=self._remaining(targets.protein, consumed.protein),
                        carbs=self._remaining(targets.carbs, consumed.carbs),
                        fat=self._remaining(targets.fat, consumed.fat),
                        fiber=self._remaining(targets.fiber, consumed.fiber),
                        water=self._remaining(targets.water, consumed.water),
                    ),
                    components=components,
                    logged_meals=[self._meal_log(log) for log in logs],
                )
            )
        return WeeklyMealsRead(**self._detail_base(context), days=days)

    def _build_goals(self, context: _WeekContext) -> WeeklyGoalsRead:
        days: list[WeeklyGoalDayRead] = []
        for point_date in self._week_dates(context):
            if point_date > context.as_of_date:
                days.append(self._future_goal_day(point_date))
                continue
            plan = context.plans[point_date]
            if plan is None or not plan.daily_goals:
                days.append(
                    WeeklyGoalDayRead(
                        date=point_date,
                        day=self._day_code(point_date),
                        is_future=False,
                        applicable=False,
                        plan=self._plan_ref(plan),
                        daily_goal_score=None,
                        completed_count=0,
                        assigned_count=0,
                        all_completed=None,
                    )
                )
                continue
            completions = {
                completion.goal_item_id: completion
                for completion in context.goal_completions
                if completion.nutrition_plan_id == plan.id and completion.goal_date == point_date
            }
            items: list[WeeklyGoalItemRead] = []
            for position, instruction in enumerate(plan.daily_goals):
                item_id = build_daily_goal_item_id(
                    nutrition_plan_id=plan.id,
                    position=position,
                    instruction=instruction,
                )
                completion = completions.get(item_id)
                items.append(
                    WeeklyGoalItemRead(
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
            days.append(
                WeeklyGoalDayRead(
                    date=point_date,
                    day=self._day_code(point_date),
                    is_future=False,
                    applicable=True,
                    plan=self._plan_ref(plan),
                    daily_goal_score=round((completed_count / total_count) * 100, 2),
                    completed_count=completed_count,
                    assigned_count=total_count,
                    all_completed=completed_count == total_count,
                    items=items,
                )
            )
        return WeeklyGoalsRead(**self._detail_base(context), days=days)

    def _ensure_managed_client(self, *, current_coach: User, client_id: UUID) -> None:
        client = self.user_repository.get_by_id(client_id)
        if client is None or client.role != UserRole.SELF:
            raise WeeklySummaryClientNotFoundError("Client not found")
        if not self.coach_client_repository.accepted_relationship_exists(
            coach_id=current_coach.id,
            client_id=client_id,
        ):
            raise WeeklySummaryClientNotManagedError("Client is not assigned to this coach")

    @staticmethod
    def _get_week_range(today: date) -> tuple[date, date]:
        week_start = today - timedelta(days=today.weekday())
        return week_start, week_start + timedelta(days=6)

    @staticmethod
    def _week_dates(context: _WeekContext) -> list[date]:
        return [context.week_start + timedelta(days=offset) for offset in range(7)]

    @staticmethod
    def _day_code(value: date) -> str:
        return value.strftime("%a").upper()

    @staticmethod
    def _plan_ref(plan: NutritionPlan | None) -> WeeklyPlanRefRead | None:
        if plan is None:
            return None
        return WeeklyPlanRefRead(
            nutrition_plan_id=plan.id,
            valid_from=plan.date,
            valid_until=nutrition_plan_valid_until(plan.date),
        )

    @staticmethod
    def _detail_base(context: _WeekContext) -> dict[str, object]:
        return {
            "user_id": context.user_id,
            "week_start": context.week_start,
            "week_end": context.week_end,
            "as_of_date": context.as_of_date,
            "as_of": context.as_of,
            "is_partial_week": context.as_of_date < context.week_end,
        }

    @staticmethod
    def _latest_workout_event(
        *,
        plan_id: UUID,
        item_id: UUID,
        point_date: date,
        events: list[WorkoutPlanCompletionEvent],
    ) -> WorkoutPlanCompletionEvent | None:
        latest = None
        for event in events:
            if (
                event.nutrition_plan_id == plan_id
                and event.workout_item_id == item_id
                and event.effective_date <= point_date
            ):
                latest = event
        return latest

    @staticmethod
    def _meal_components(
        *,
        targets: WeeklyMealTargetsRead,
        consumed: WeeklyMealTotalsRead,
    ) -> list[WeeklyMealComponentRead]:
        specs = [
            ("KCAL", targets.kcal, consumed.kcal),
            ("PROTEIN", targets.protein, consumed.protein),
            ("CARBS", targets.carbs, consumed.carbs),
            ("FAT", targets.fat, consumed.fat),
            ("FIBER", targets.fiber, consumed.fiber),
        ]
        components: list[WeeklyMealComponentRead] = []
        for name, target, actual in specs:
            if target is None:
                continue
            attainment = WeeklySummaryService._attainment(target=target, actual=actual)
            components.append(
                WeeklyMealComponentRead(
                    name=name,
                    target=target,
                    consumed=actual,
                    attainment_percent=attainment,
                    met=attainment >= 100.0,
                )
            )
        return components

    @staticmethod
    def _attainment(*, target: float, actual: float) -> float:
        if target == 0:
            return 100.0 if actual == 0 else 0.0
        return round(min(max(actual, 0.0) / target, 1.0) * 100, 2)

    @staticmethod
    def _remaining(target: float | None, actual: float) -> float | None:
        return round(target - actual, 2) if target is not None else None

    @staticmethod
    def _meal_log(log: RoutineMacroLog) -> WeeklyMealLogRead:
        return WeeklyMealLogRead(
            id=log.id,
            meal_type=log.meal_type,
            food_name=log.food_name,
            amount=log.amount,
            amount_unit=log.amount_unit,
            kcal=log.kcal,
            protein=log.protein,
            carbs=log.carbs,
            fat=log.fat,
            fiber=log.fiber,
            logged_at=log.logged_at,
        )

    @staticmethod
    def _future_workout_day(point_date: date) -> WeeklyWorkoutDayRead:
        return WeeklyWorkoutDayRead(
            date=point_date,
            day=WeeklySummaryService._day_code(point_date),
            is_future=True,
            applicable=False,
            plan=None,
            workout_score=None,
            completed_count=0,
            assigned_count=0,
            all_completed=None,
        )

    @staticmethod
    def _future_meal_day(point_date: date) -> WeeklyMealDayRead:
        empty_targets = WeeklyMealTargetsRead(
            kcal=None,
            protein=None,
            carbs=None,
            fat=None,
            fiber=None,
            water=None,
        )
        empty_totals = WeeklyMealTotalsRead(
            kcal=0.0,
            protein=0.0,
            carbs=0.0,
            fat=0.0,
            fiber=0.0,
            water=0.0,
        )
        return WeeklyMealDayRead(
            date=point_date,
            day=WeeklySummaryService._day_code(point_date),
            is_future=True,
            applicable=False,
            plan=None,
            routine_id=None,
            meal_score=None,
            components_scored=0,
            components_met=0,
            completed=None,
            targets=empty_targets,
            consumed=empty_totals,
            remaining=WeeklyMealRemainingRead(
                kcal=None,
                protein=None,
                carbs=None,
                fat=None,
                fiber=None,
                water=None,
            ),
        )

    @staticmethod
    def _future_goal_day(point_date: date) -> WeeklyGoalDayRead:
        return WeeklyGoalDayRead(
            date=point_date,
            day=WeeklySummaryService._day_code(point_date),
            is_future=True,
            applicable=False,
            plan=None,
            daily_goal_score=None,
            completed_count=0,
            assigned_count=0,
            all_completed=None,
        )

    @staticmethod
    def _average_score(points: list[DailyProgressPoint], field_name: str) -> float | None:
        values = [
            value for point in points if (value := getattr(point, field_name)) is not None
        ]
        return round(sum(values) / len(values), 2) if values else None
