from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProfileRead(BaseModel):
    id: UUID
    email: str
    name: str = Field(validation_alias="full_name")
    age: int | None
    occupation: str | None
    fitness_goal: str | None
    profile_image: str | None
    reference_image: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ProfilePutRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    age: int | None = Field(ge=0)
    occupation: str | None
    fitness_goal: str | None
    profile_image: str | None
    reference_image: str | None


class ProfilePatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    age: int | None = Field(default=None, ge=0)
    occupation: str | None = None
    fitness_goal: str | None = None
    profile_image: str | None = None
    reference_image: str | None = None