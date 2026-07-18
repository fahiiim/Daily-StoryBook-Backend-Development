from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class AddCoachClientRequest(BaseModel):
    client_email: EmailStr


class CoachClientRead(BaseModel):
    id: UUID
    coach_id: UUID
    client_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)