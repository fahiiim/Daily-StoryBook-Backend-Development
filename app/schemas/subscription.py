from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.subscription import SubscriptionStatus


class SubscriptionRead(BaseModel):
    id: UUID
    user_id: UUID
    plan_name: str
    status: SubscriptionStatus
    current_period_end: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
