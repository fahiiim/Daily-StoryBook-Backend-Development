from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.storybook import StorybookStatus
from app.schemas.nutrition_plan import NutritionPlanRead
from app.schemas.routine import RoutineRead
from app.schemas.weekly_summary import WeeklySummaryRead
from app.schemas.workout_plan import WorkoutPlanRead


class StorybookSummary(BaseModel):
    id: UUID
    date: date
    status: StorybookStatus
    pdf_url: str | None
    generated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ClientDashboardResponse(BaseModel):
    client_id: UUID
    today_routine: RoutineRead | None
    today_storybook: StorybookSummary | None
    weekly_progress: WeeklySummaryRead | None
    workout_plans: list[WorkoutPlanRead] = Field(default_factory=list)
    nutrition_plans: list[NutritionPlanRead] = Field(default_factory=list)
    subscription: dict[str, object] = Field(default_factory=dict)
    notifications: list[dict[str, object]] = Field(default_factory=list)
    statistics: dict[str, object] = Field(default_factory=dict)


class CoachWeeklyCompletion(BaseModel):
    completed_routines: int
    total_routines: int
    completion_rate: float


class CoachActivity(BaseModel):
    activity_type: str
    user_id: UUID
    user_name: str
    occurred_at: datetime
    description: str | None = None


class CoachClientOverview(BaseModel):
    user_id: UUID
    full_name: str
    email: str
    last_routine_date: date | None
    last_storybook_status: StorybookStatus | None
    week_completion_rate: float | None


class CoachDashboardResponse(BaseModel):
    total_clients: int
    stories_generated_today: int
    pending_stories: int
    weekly_completion: CoachWeeklyCompletion
    recent_activities: list[CoachActivity] = Field(default_factory=list)
    client_overview: list[CoachClientOverview] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    coach_dashboard: CoachDashboardResponse | None = None
    client_dashboard: ClientDashboardResponse | None = None
