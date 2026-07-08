from datetime import date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.models.user import UserRole


def _validate_date_of_birth(value: date | None) -> date | None:
    if value is None:
        return None

    today = date.today()
    if value >= today:
        raise ValueError("date_of_birth must be in the past")

    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age > 120:
        raise ValueError("date_of_birth implies an age greater than 120")

    return value


class ProfileRead(BaseModel):
    id: UUID
    username: str
    email: str
    name: str = Field(validation_alias="full_name")
    role: UserRole | None
    date_of_birth: date | None
    occupation: str | None
    fitness_goal: str | None
    bio: str | None
    profile_image: str | None
    reference_image: str | None
    use_reference_image: bool
    is_email_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @computed_field(return_type=int | None)
    @property
    def age(self) -> int | None:
        if self.date_of_birth is None:
            return None

        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class ProfilePutRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    date_of_birth: date | None = None
    occupation: str | None
    fitness_goal: str | None
    bio: str | None = Field(default=None, max_length=500)
    profile_image: str | None
    reference_image: str | None
    use_reference_image: bool = False

    _validate_dob = field_validator("date_of_birth")(_validate_date_of_birth)


class ProfilePatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    date_of_birth: date | None = None
    occupation: str | None = None
    fitness_goal: str | None = None
    bio: str | None = Field(default=None, max_length=500)
    profile_image: str | None = None
    reference_image: str | None = None
    use_reference_image: bool | None = None

    _validate_dob = field_validator("date_of_birth")(_validate_date_of_birth)