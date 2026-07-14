from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserRead


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


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=255, examples=["strong-password"])
    full_name: str = Field(min_length=1, max_length=255, examples=["Alex Doe"])
    role: Literal["SELF", "COACH"]
    date_of_birth: date | None = Field(default=None, examples=["2000-01-01"])
    gender: str | None = Field(default=None, max_length=50)
    occupation: str | None = None
    fitness_goal: str | None = None
    wake_up_time: str | None = Field(default=None, max_length=16)
    bed_time: str | None = Field(default=None, max_length=16)
    height: str | None = Field(default=None, max_length=64)
    weight: float | None = Field(default=None, ge=0)
    target_weight: float | None = Field(default=None, ge=0)
    short_bio: str | None = Field(default=None, max_length=500)
    fitness_motivation: str | None = Field(default=None, max_length=500)
    profile_image: str | None = None
    reference_image: str | None = None

    _validate_dob = field_validator("date_of_birth")(_validate_date_of_birth)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=255, examples=["strong-password"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterResponse(BaseModel):
    user: UserRead


class RegistrationInfoPatchRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    date_of_birth: date | None = Field(default=None, examples=["2000-01-01"])
    gender: str | None = Field(default=None, max_length=50)
    fitness_goal: str | None = None
    wake_up_time: str | None = Field(default=None, max_length=16)
    bed_time: str | None = Field(default=None, max_length=16)
    height: str | None = Field(default=None, max_length=64)
    weight: float | None = Field(default=None, ge=0)
    target_weight: float | None = Field(default=None, ge=0)
    short_bio: str | None = Field(default=None, max_length=500)
    fitness_motivation: str | None = Field(default=None, max_length=500)
    profile_image: str | None = None
    reference_image: str | None = None

    _validate_dob = field_validator("date_of_birth")(_validate_date_of_birth)


class RegistrationInfoResponse(BaseModel):
    user: UserRead