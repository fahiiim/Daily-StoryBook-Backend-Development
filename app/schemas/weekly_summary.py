from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WeeklySummaryRead(BaseModel):
    id: UUID
    user_id: UUID
    week_start: date
    week_end: date
    summary: str
    image_url: str | None
    generated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeeklySummaryGenerateRequest(BaseModel):
    user_id: UUID | None = None


class WeeklySummaryGenerateResponse(BaseModel):
    summary: WeeklySummaryRead


class WeeklySummaryHistoryResponse(BaseModel):
    summaries: list[WeeklySummaryRead] = Field(default_factory=list)