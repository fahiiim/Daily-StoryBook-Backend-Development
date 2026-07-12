from datetime import date as dt_date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.routine_macro_log import MacroType


class RoutineMacroInput(BaseModel):
    meals_kcal: float | None = Field(default=None, ge=0)
    goal_kcal: float | None = Field(default=None, ge=0)
    goal_protein: float | None = Field(default=None, ge=0)
    goal_carbs: float | None = Field(default=None, ge=0)
    goal_fats: float | None = Field(default=None, ge=0)
    goal_fiber: float | None = Field(default=None, ge=0)
    intake_protein: float | None = Field(default=None, ge=0)
    intake_carbs: float | None = Field(default=None, ge=0)
    intake_fats: float | None = Field(default=None, ge=0)
    intake_fiber: float | None = Field(default=None, ge=0)


class RoutineCreate(RoutineMacroInput):
    date: dt_date
    workout: str | None = None
    meals: str | None = None
    water_intake: float | None = Field(default=None, ge=0)
    sleep: float | None = Field(default=None, ge=0)
    notes: str | None = None
    completion_status: bool = False


class RoutinePut(RoutineMacroInput):
    date: dt_date
    workout: str | None = None
    meals: str | None = None
    water_intake: float | None = Field(default=None, ge=0)
    sleep: float | None = Field(default=None, ge=0)
    notes: str | None = None
    completion_status: bool


class RoutinePatch(RoutineMacroInput):
    date: dt_date | None = None
    workout: str | None = None
    meals: str | None = None
    water_intake: float | None = Field(default=None, ge=0)
    sleep: float | None = Field(default=None, ge=0)
    notes: str | None = None
    completion_status: bool | None = None


class RoutineRead(BaseModel):
    id: UUID
    user_id: UUID
    date: dt_date
    workout: str | None
    meals: str | None
    meals_kcal: float | None
    goal_kcal: float | None
    goal_protein: float | None
    goal_carbs: float | None
    goal_fats: float | None
    goal_fiber: float | None
    intake_protein: float | None
    intake_carbs: float | None
    intake_fats: float | None
    intake_fiber: float | None
    water_intake: float | None
    sleep: float | None
    notes: str | None
    completion_status: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field(return_type=float | None)
    @property
    def consumed_kcal(self) -> float | None:
        if self.meals_kcal is not None:
            return round(self.meals_kcal, 2)

        parts = [
            self.intake_protein,
            self.intake_carbs,
            self.intake_fats,
            self.intake_fiber,
        ]
        if all(value is None for value in parts):
            return None

        total = (
            (self.intake_protein or 0.0) * 4
            + (self.intake_carbs or 0.0) * 4
            + (self.intake_fats or 0.0) * 9
            + (self.intake_fiber or 0.0) * 2
        )
        return round(total, 2)

    @computed_field(return_type=float | None)
    @property
    def remaining_kcal(self) -> float | None:
        if self.goal_kcal is None:
            return None
        return round(self.goal_kcal - (self.consumed_kcal or 0.0), 2)

    @computed_field(return_type=float | None)
    @property
    def remaining_protein(self) -> float | None:
        if self.goal_protein is None:
            return None
        return round(self.goal_protein - (self.intake_protein or 0.0), 2)

    @computed_field(return_type=float | None)
    @property
    def remaining_carbs(self) -> float | None:
        if self.goal_carbs is None:
            return None
        return round(self.goal_carbs - (self.intake_carbs or 0.0), 2)

    @computed_field(return_type=float | None)
    @property
    def remaining_fats(self) -> float | None:
        if self.goal_fats is None:
            return None
        return round(self.goal_fats - (self.intake_fats or 0.0), 2)

    @computed_field(return_type=float | None)
    @property
    def remaining_fiber(self) -> float | None:
        if self.goal_fiber is None:
            return None
        return round(self.goal_fiber - (self.intake_fiber or 0.0), 2)


class RoutineMacroLogCreate(BaseModel):
    macro_type: MacroType
    food_name: str = Field(min_length=1, max_length=255)
    amount: float = Field(gt=0)
    amount_unit: str = Field(default="grams", min_length=1, max_length=32)
    macro_grams: float = Field(ge=0)
    kcal: float = Field(ge=0)
    logged_at: datetime | None = None


class RoutineMacroLogRead(BaseModel):
    id: UUID
    routine_id: UUID
    user_id: UUID
    macro_type: MacroType
    food_name: str
    amount: float
    amount_unit: str
    macro_grams: float
    kcal: float
    logged_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoutineRecentFoodRead(BaseModel):
    macro_type: MacroType
    food_name: str
    amount: float
    amount_unit: str
    macro_grams: float
    kcal: float
    last_logged_at: datetime


class RoutineMacroLogCreateResponse(BaseModel):
    routine: RoutineRead
    log: RoutineMacroLogRead