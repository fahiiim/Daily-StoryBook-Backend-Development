from datetime import date as dt_date
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PlanInstruction = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class NutritionPlanBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    daily_calories: int | None = Field(default=None, ge=0)
    protein: float | None = Field(default=None, ge=0)
    carbs: float | None = Field(default=None, ge=0)
    fat: float | None = Field(default=None, ge=0)
    fiber: float | None = Field(default=None, ge=0)
    water_goal: float | None = Field(default=None, ge=0)
    workout_plan: list[PlanInstruction] = Field(
        default_factory=list,
        description="Ordered exercise instructions with no application-level item limit",
    )
    daily_goals: list[PlanInstruction] = Field(
        default_factory=list,
        description="Ordered daily goals with no application-level item limit",
    )
    notes: str | None = None
    date: dt_date


class NutritionPlanCreate(NutritionPlanBase):
    pass


class NutritionPlanPut(NutritionPlanBase):
    workout_plan: list[PlanInstruction]
    daily_goals: list[PlanInstruction]


class NutritionPlanRead(BaseModel):
    id: UUID
    coach_id: UUID
    client_id: UUID
    daily_calories: int | None
    protein: float | None
    carbs: float | None
    fat: float | None
    fiber: float | None
    water_goal: float | None
    workout_plan: list[str]
    daily_goals: list[str]
    notes: str | None
    date: dt_date
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)