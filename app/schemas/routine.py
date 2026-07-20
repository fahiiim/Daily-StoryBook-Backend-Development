from datetime import date as dt_date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.models.routine_macro_log import MacroType, MealType
from app.schemas.nutrition_plan import NutritionPlanRead


class RoutineMacroInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    nutrition_plan: NutritionPlanRead | None = None

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
    model_config = ConfigDict(extra="forbid")

    meal_type: MealType
    food_name: str = Field(min_length=1, max_length=255)
    amount: float = Field(default=1.0, gt=0)
    amount_unit: str = Field(default="serving", min_length=1, max_length=32)
    kcal: float = Field(ge=0)
    protein: float = Field(default=0.0, ge=0)
    carbs: float = Field(default=0.0, ge=0)
    fat: float = Field(default=0.0, ge=0)
    fiber: float = Field(default=0.0, ge=0)
    logged_at: datetime | None = None

    @field_validator("food_name", "amount_unit")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


class RoutineMacroLogUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meal_type: MealType | None = None
    food_name: str | None = Field(default=None, min_length=1, max_length=255)
    amount: float | None = Field(default=None, gt=0)
    amount_unit: str | None = Field(default=None, min_length=1, max_length=32)
    kcal: float | None = Field(default=None, ge=0)
    protein: float | None = Field(default=None, ge=0)
    carbs: float | None = Field(default=None, ge=0)
    fat: float | None = Field(default=None, ge=0)
    fiber: float | None = Field(default=None, ge=0)
    logged_at: datetime | None = None

    @field_validator("food_name", "amount_unit")
    @classmethod
    def validate_optional_non_blank_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @model_validator(mode="after")
    def validate_update_fields(self):
        if not self.model_fields_set:
            raise ValueError("At least one meal field must be provided")
        if any(getattr(self, field_name) is None for field_name in self.model_fields_set):
            raise ValueError("Meal fields cannot be null")
        return self


class RoutineMacroLogRead(BaseModel):
    id: UUID
    routine_id: UUID
    user_id: UUID
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

    model_config = ConfigDict(from_attributes=True)


class RoutineRecentFoodRead(BaseModel):
    macro_type: MacroType
    food_name: str
    amount: float
    amount_unit: str
    kcal: float
    protein: float
    carbs: float
    fat: float
    fiber: float
    last_logged_at: datetime


class RoutineMacroLogCreateResponse(BaseModel):
    routine: RoutineRead
    log: RoutineMacroLogRead


class RoutineMacroTotalsRead(BaseModel):
    kcal: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat: float = 0.0
    fiber: float = 0.0
    water: float = 0.0


class RoutineMacroRemainingRead(BaseModel):
    kcal: float | None = None
    protein: float | None = None
    carbs: float | None = None
    fat: float | None = None
    fiber: float | None = None
    water: float | None = None


class RoutineDashboardRead(BaseModel):
    date: dt_date
    routine: RoutineRead | None
    nutrition_plan: NutritionPlanRead | None
    totals: RoutineMacroTotalsRead
    remaining: RoutineMacroRemainingRead
    logged_meals: list[RoutineMacroLogRead] = Field(default_factory=list)