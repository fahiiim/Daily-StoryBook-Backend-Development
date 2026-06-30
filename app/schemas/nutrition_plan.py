from datetime import date as dt_date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NutritionPlanBase(BaseModel):
    client_id: UUID
    breakfast: str | None = None
    lunch: str | None = None
    dinner: str | None = None
    snacks: str | None = None
    daily_calories: int | None = Field(default=None, ge=0)
    protein: float | None = Field(default=None, ge=0)
    carbs: float | None = Field(default=None, ge=0)
    fat: float | None = Field(default=None, ge=0)
    water_goal: float | None = Field(default=None, ge=0)
    notes: str | None = None
    date: dt_date


class NutritionPlanCreate(NutritionPlanBase):
    pass


class NutritionPlanPut(NutritionPlanBase):
    pass


class NutritionPlanRead(BaseModel):
    id: UUID
    coach_id: UUID
    client_id: UUID
    breakfast: str | None
    lunch: str | None
    dinner: str | None
    snacks: str | None
    daily_calories: int | None
    protein: float | None
    carbs: float | None
    fat: float | None
    water_goal: float | None
    notes: str | None
    date: dt_date
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)