from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    email: str
    full_name: str
    age: int | None = Field(default=None, ge=0)
    gender: str | None = None
    occupation: str | None = None
    fitness_goal: str | None = None
    profile_image: str | None = None
    reference_image: str | None = None
    role: UserRole = UserRole.SELF
    is_active: bool = True


class UserCreate(UserBase):
    hashed_password: str = Field(min_length=8, max_length=255)


class UserUpdate(BaseModel):
    full_name: str | None = None
    age: int | None = Field(default=None, ge=0)
    gender: str | None = None
    occupation: str | None = None
    fitness_goal: str | None = None
    profile_image: str | None = None
    reference_image: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    hashed_password: str | None = Field(default=None, min_length=8, max_length=255)


class UserRead(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)