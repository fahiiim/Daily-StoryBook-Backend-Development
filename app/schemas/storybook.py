from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.storybook import StorybookStatus


class StoryPageRead(BaseModel):
    id: UUID
    storybook_id: UUID
    page_number: int = Field(ge=1)
    story: str | None
    image_url: str | None
    is_edited: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StorybookRead(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    status: StorybookStatus
    pdf_url: str | None
    generated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    pages: list[StoryPageRead] = []

    model_config = ConfigDict(from_attributes=True)


class StorybookGenerateResponse(BaseModel):
    storybook_id: UUID


class StorybookPdfResponse(BaseModel):
    pdf_url: str


class StoryPageUpdateRequest(BaseModel):
    story: str = Field(min_length=1)
