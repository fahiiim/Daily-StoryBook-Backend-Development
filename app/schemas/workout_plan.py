from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkoutPlanCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    exercises: str | None = None
    is_active: bool = True


class WorkoutPlanPut(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    exercises: str | None = None
    is_active: bool


class WorkoutPlanPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    exercises: str | None = None
    is_active: bool | None = None


class WorkoutPlanRead(BaseModel):
    id: UUID
    coach_id: UUID
    title: str
    description: str | None
    exercises: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkoutPlanAssignRequest(BaseModel):
    client_id: UUID


class WorkoutPlanAssignmentRead(BaseModel):
    id: UUID
    plan_id: UUID
    client_id: UUID
    assigned_by_coach_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)