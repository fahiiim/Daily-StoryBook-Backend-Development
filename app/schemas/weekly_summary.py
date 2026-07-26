from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WeeklySummaryRead(BaseModel):
    id: UUID
    user_id: UUID
    week_start: date
    week_end: date
    summary: str
    image_url: str | None
    generated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeeklySummaryGenerateRequest(BaseModel):
    user_id: UUID | None = None


class WeeklySummaryGenerateResponse(BaseModel):
    summary: WeeklySummaryRead


class WeeklySummaryHistoryResponse(BaseModel):
    summaries: list[WeeklySummaryRead] = Field(default_factory=list)


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


class DailyGoalCompletionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed: bool


class DailyGoalItemRead(BaseModel):
    id: UUID
    position: int = Field(ge=0)
    instruction: str
    completed: bool
    completed_at: datetime | None


class DailyGoalsTodayRead(BaseModel):
    nutrition_plan_id: UUID
    goal_date: date
    items: list[DailyGoalItemRead] = Field(default_factory=list)
    completed_count: int
    total_count: int
    completion_rate: float
    all_completed: bool