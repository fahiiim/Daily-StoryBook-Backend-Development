from datetime import date as dt_date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.user import UserRole


class UserBase(BaseModel):
    username: str
    email: str
    full_name: str
    date_of_birth: dt_date | None = None
    gender: str | None = None
    occupation: str | None = None
    fitness_goal: str | None = None
    bio: str | None = None
    profile_image: str | None = None
    reference_image: str | None = None
    use_reference_image: bool = False
    role: UserRole | None = None
    is_email_verified: bool = False
    is_active: bool = True


class UserCreate(UserBase):
    hashed_password: str = Field(min_length=8, max_length=255)


class UserUpdate(BaseModel):
    username: str | None = None
    full_name: str | None = None
    date_of_birth: dt_date | None = None
    gender: str | None = None
    occupation: str | None = None
    fitness_goal: str | None = None
    bio: str | None = None
    profile_image: str | None = None
    reference_image: str | None = None
    use_reference_image: bool | None = None
    role: UserRole | None = None
    is_email_verified: bool | None = None
    is_active: bool | None = None
    hashed_password: str | None = Field(default=None, min_length=8, max_length=255)


class UserRead(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field(return_type=int | None)
    @property
    def age(self) -> int | None:
        if self.date_of_birth is None:
            return None

        today = dt_date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )