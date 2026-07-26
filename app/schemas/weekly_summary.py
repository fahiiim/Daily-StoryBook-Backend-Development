from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
