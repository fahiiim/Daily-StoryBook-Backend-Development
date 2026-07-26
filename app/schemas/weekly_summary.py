from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from app.models.routine_macro_log import MealType


class DailyProgressPoint(BaseModel):
    date: date
    day: str
    workout_score: float | None
    meal_score: float | None
    daily_goal_score: float | None
    combined_score: float | None
    workout_completed: int = 0
    workout_assigned: int = 0
    meal_components_scored: int = 0
    daily_goals_completed: int = 0
    daily_goals_assigned: int = 0
    workout_applicable: bool = False
    meal_applicable: bool = False
    daily_goal_applicable: bool = False
    is_future: bool = False


class WeeklyProgressAverages(BaseModel):
    workout_score: float | None
    meal_score: float | None
    daily_goal_score: float | None
    combined_score: float | None
    ending_workout_completion_rate: float | None


class WeeklyProgressCoverage(BaseModel):
    elapsed_days: int
    workout_days_scored: int
    meal_days_scored: int
    daily_goal_days_scored: int
    combined_days_scored: int
    complete: bool


class WeeklyProgressAnalyticsRead(BaseModel):
    user_id: UUID
    week_start: date
    week_end: date
    as_of_date: date
    as_of: datetime
    week_starts_on: str = "MONDAY"
    scoring_version: str = "v1"
    is_partial_week: bool
    daily_points: list[DailyProgressPoint] = Field(default_factory=list)
    weekly_averages: WeeklyProgressAverages
    coverage: WeeklyProgressCoverage

    @computed_field(return_type=float | None)
    @property
    def weekly_progress_percentage(self) -> float | None:
        return self.weekly_averages.combined_score


class WeeklyPlanRefRead(BaseModel):
    nutrition_plan_id: UUID
    valid_from: date
    valid_until: date


class WeeklyDetailBaseRead(BaseModel):
    user_id: UUID
    week_start: date
    week_end: date
    as_of_date: date
    as_of: datetime
    is_partial_week: bool


class WeeklyWorkoutItemRead(BaseModel):
    id: UUID
    position: int
    instruction: str
    completed: bool
    state_effective_date: date | None
    state_changed_at: datetime | None


class WeeklyWorkoutDayRead(BaseModel):
    date: date
    day: str
    is_future: bool
    applicable: bool
    plan: WeeklyPlanRefRead | None
    workout_score: float | None
    completed_count: int
    assigned_count: int
    all_completed: bool | None
    items: list[WeeklyWorkoutItemRead] = Field(default_factory=list)


class WeeklyWorkoutsRead(WeeklyDetailBaseRead):
    days: list[WeeklyWorkoutDayRead] = Field(default_factory=list)


class WeeklyMealTargetsRead(BaseModel):
    kcal: float | None
    protein: float | None
    carbs: float | None
    fat: float | None
    fiber: float | None
    water: float | None


class WeeklyMealTotalsRead(BaseModel):
    kcal: float
    protein: float
    carbs: float
    fat: float
    fiber: float
    water: float


class WeeklyMealRemainingRead(BaseModel):
    kcal: float | None
    protein: float | None
    carbs: float | None
    fat: float | None
    fiber: float | None
    water: float | None


class WeeklyMealComponentRead(BaseModel):
    name: str
    target: float
    consumed: float
    attainment_percent: float
    met: bool


class WeeklyMealLogRead(BaseModel):
    id: UUID
    meal_type: MealType
    food_name: str
    amount: float
    amount_unit: str
    kcal: float
    protein: float
    carbs: float
    fat: float
    fiber: float
    logged_at: datetime


class WeeklyMealDayRead(BaseModel):
    date: date
    day: str
    is_future: bool
    applicable: bool
    plan: WeeklyPlanRefRead | None
    routine_id: UUID | None
    meal_score: float | None
    components_scored: int
    components_met: int
    completed: bool | None
    targets: WeeklyMealTargetsRead
    consumed: WeeklyMealTotalsRead
    remaining: WeeklyMealRemainingRead
    components: list[WeeklyMealComponentRead] = Field(default_factory=list)
    logged_meals: list[WeeklyMealLogRead] = Field(default_factory=list)


class WeeklyMealsRead(WeeklyDetailBaseRead):
    days: list[WeeklyMealDayRead] = Field(default_factory=list)


class WeeklyGoalItemRead(BaseModel):
    id: UUID
    position: int
    instruction: str
    completed: bool
    completed_at: datetime | None


class WeeklyGoalDayRead(BaseModel):
    date: date
    day: str
    is_future: bool
    applicable: bool
    plan: WeeklyPlanRefRead | None
    daily_goal_score: float | None
    completed_count: int
    assigned_count: int
    all_completed: bool | None
    items: list[WeeklyGoalItemRead] = Field(default_factory=list)


class WeeklyGoalsRead(WeeklyDetailBaseRead):
    days: list[WeeklyGoalDayRead] = Field(default_factory=list)
