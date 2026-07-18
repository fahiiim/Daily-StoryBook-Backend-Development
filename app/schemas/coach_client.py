from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AddCoachClientRequest(BaseModel):
    client_email: EmailStr
    personalized_message: str | None = Field(default=None, max_length=1000)
    assign_initial_plan: bool = False


class CoachClientRead(BaseModel):
    id: UUID
    coach_id: UUID
    client_id: UUID
    personalized_message: str | None
    assign_initial_plan: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)