from datetime import date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.models.user import UserRole
from app.schemas.subscription import SubscriptionRead


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


class SelfProfileRead(BaseModel):
    id: UUID
    email: str
    name: str
    role: UserRole
    date_of_birth: date | None
    bio: str | None
    profile_image: str | None
    reference_image: str | None
    use_reference_image: bool
    subscription_plan: SubscriptionRead | None = None
    is_email_verified: bool
    created_at: datetime
    updated_at: datetime

    @computed_field(return_type=int | None)
    @property
    def age(self) -> int | None:
        if self.date_of_birth is None:
            return None

        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class SelfProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    date_of_birth: date | None = None
    bio: str | None = Field(default=None, max_length=500)
    profile_image: str | None = None
    reference_image: str | None = None
    use_reference_image: bool | None = None

    _validate_dob = field_validator("date_of_birth")(_validate_date_of_birth)


class CoachSettingsRead(BaseModel):
    id: UUID
    email: str
    name: str
    role: UserRole
    phone_number: str | None
    bio: str | None
    updated_at: datetime


class CoachSettingsUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone_number: str | None = Field(default=None, min_length=3, max_length=32)
    bio: str | None = Field(default=None, max_length=500)


class PasswordUpdateRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)
    confirm_password: str = Field(min_length=8, max_length=255)

    @model_validator(mode="after")
    def validate_password_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match")
        return self


class ClientManagementLimitsRead(BaseModel):
    max_client_capacity: int = Field(ge=0)
    current_clients: int = Field(ge=0)

    @computed_field(return_type=int)
    @property
    def remaining_client_capacity(self) -> int:
        return max(self.max_client_capacity - self.current_clients, 0)


class ProfileMessageResponse(BaseModel):
    message: str