from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkoutCompletionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed: bool


class AssignedWorkoutItemRead(BaseModel):
    id: UUID
    position: int = Field(ge=0)
    instruction: str
    completed: bool
    completed_at: datetime | None


class AssignedWorkoutPlanRead(BaseModel):
    nutrition_plan_id: UUID
    coach_id: UUID
    client_id: UUID
    valid_from: date
    valid_until: date
    validity_days: int
    items: list[AssignedWorkoutItemRead] = Field(default_factory=list)
    completed_count: int = 0
    total_count: int = 0
    completion_rate: float = 0.0
    all_completed: bool = False
