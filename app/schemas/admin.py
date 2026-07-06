from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.storybook import StorybookStatus
from app.schemas.storybook import StorybookRead
from app.schemas.subscription import SubscriptionRead
from app.schemas.user import UserRead


class AdminDashboardResponse(BaseModel):
    total_users: int
    active_users: int
    total_coaches: int
    stories_generated: int
    subscriptions: int
    storage_usage_bytes: int


class AdminUserListResponse(BaseModel):
    items: list[UserRead] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class AdminStorybookSummary(BaseModel):
    id: UUID
    user_id: UUID
    date: datetime
    status: StorybookStatus
    pdf_url: str | None
    generated_at: datetime | None
    created_at: datetime


class AdminStorybookListResponse(BaseModel):
    items: list[StorybookRead] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class AdminSubscriptionListResponse(BaseModel):
    items: list[SubscriptionRead] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
