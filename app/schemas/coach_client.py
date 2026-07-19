from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.coach_client import CoachClientStatus


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
    status: CoachClientStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CoachClientSentRequestRead(BaseModel):
    id: UUID
    coach_id: UUID
    client_id: UUID
    client_email: EmailStr
    client_name: str
    personalized_message: str | None
    assign_initial_plan: bool
    status: CoachClientStatus
    created_at: datetime