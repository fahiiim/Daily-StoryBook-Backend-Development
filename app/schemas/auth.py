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
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        examples=["alex_doe"],
    )
    email: EmailStr
    password: str = Field(min_length=8, max_length=255, examples=["strong-password"])
    full_name: str = Field(min_length=1, max_length=255, examples=["Alex Doe"])
    role: Literal["SELF", "COACH"]
    date_of_birth: date | None = None
    gender: str | None = None
    occupation: str | None = None
    fitness_goal: str | None = None
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
    otp: str = Field(pattern=r"^\d{6}$")