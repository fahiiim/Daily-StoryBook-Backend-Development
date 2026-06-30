from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AddCoachClientRequest(BaseModel):
    client_id: UUID


class CoachClientRead(BaseModel):
    id: UUID
    coach_id: UUID
    client_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)