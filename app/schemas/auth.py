from pydantic import BaseModel, Field

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, examples=["user@example.com"])
    password: str = Field(min_length=8, max_length=255, examples=["strong-password"])
    full_name: str = Field(min_length=1, max_length=255, examples=["Alex Doe"])
    age: int | None = Field(default=None, ge=0)
    gender: str | None = None
    occupation: str | None = None
    fitness_goal: str | None = None
    profile_image: str | None = None
    reference_image: str | None = None
    role: UserRole = UserRole.SELF
    is_active: bool = True


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, examples=["user@example.com"])
    password: str = Field(min_length=8, max_length=255, examples=["strong-password"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"