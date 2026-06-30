from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RoutineCreate(BaseModel):
    date: date
    workout: str | None = None
    meals: str | None = None
    water_intake: float | None = Field(default=None, ge=0)
    sleep: float | None = Field(default=None, ge=0)
    notes: str | None = None
    completion_status: bool = False


class RoutinePut(BaseModel):
    date: date
    workout: str | None = None
    meals: str | None = None
    water_intake: float | None = Field(default=None, ge=0)
    sleep: float | None = Field(default=None, ge=0)
    notes: str | None = None
    completion_status: bool


class RoutinePatch(BaseModel):
    date: date | None = None
    workout: str | None = None
    meals: str | None = None
    water_intake: float | None = Field(default=None, ge=0)
    sleep: float | None = Field(default=None, ge=0)
    notes: str | None = None
    completion_status: bool | None = None


class RoutineRead(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    workout: str | None
    meals: str | None
    water_intake: float | None
    sleep: float | None
    notes: str | None
    completion_status: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)