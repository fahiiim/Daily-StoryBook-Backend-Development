from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.json_schema import SkipJsonSchema

ExerciseInstruction = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _remove_schema_default(schema: dict[str, Any]) -> None:
    schema.pop("default", None)


class WorkoutPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    exercises: list[ExerciseInstruction] = Field(
        default_factory=list,
        description="Ordered exercise instructions with no application-level item limit",
    )
    is_active: bool = True


class WorkoutPlanPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    exercises: list[ExerciseInstruction]
    is_active: bool


class WorkoutPlanPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | SkipJsonSchema[None] = Field(
        default=None,
        min_length=1,
        max_length=255,
        json_schema_extra=_remove_schema_default,
    )
    description: str | None = None
    exercises: list[ExerciseInstruction] | SkipJsonSchema[None] = Field(
        default=None,
        json_schema_extra=_remove_schema_default,
    )
    is_active: bool | SkipJsonSchema[None] = Field(
        default=None,
        json_schema_extra=_remove_schema_default,
    )

    @model_validator(mode="after")
    def validate_non_nullable_fields(self):
        for field_name in ("title", "exercises", "is_active"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class WorkoutPlanRead(BaseModel):
    id: UUID
    coach_id: UUID
    title: str
    description: str | None
    exercises: list[str]
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