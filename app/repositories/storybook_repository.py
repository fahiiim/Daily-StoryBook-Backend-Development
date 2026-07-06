from datetime import date
from uuid import UUID
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.storybook import Storybook, StoryPage


class StorybookRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, storybook: Storybook, commit: bool = True) -> Storybook:
        self.db.add(storybook)
        if commit:
            self.db.commit()
            self.db.refresh(storybook)
        else:
            self.db.flush()
            self.db.refresh(storybook)
        return storybook

    def get_by_id(self, *, storybook_id: UUID) -> Storybook | None:
        statement = select(Storybook).where(Storybook.id == storybook_id)
        return self.db.scalar(statement)

    def list_by_user_between_dates(
        self,
        *,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[Storybook]:
        statement = (
            select(Storybook)
            .where(
                Storybook.user_id == user_id,
                Storybook.date >= start_date,
                Storybook.date <= end_date,
            )
            .order_by(Storybook.date.desc(), Storybook.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def update_fields(self, *, storybook: Storybook, updates: dict[str, Any], commit: bool = True) -> Storybook:
        for field_name, value in updates.items():
            setattr(storybook, field_name, value)

        self.db.add(storybook)
        if commit:
            self.db.commit()
            self.db.refresh(storybook)
        else:
            self.db.flush()
            self.db.refresh(storybook)
        return storybook


class StoryPageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_pages(self, *, pages: list[StoryPage], commit: bool = True) -> None:
        if not pages:
            return
        self.db.add_all(pages)
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def list_by_storybook(self, *, storybook_id: UUID) -> list[StoryPage]:
        statement = (
            select(StoryPage)
            .where(StoryPage.storybook_id == storybook_id)
            .order_by(StoryPage.page_number.asc())
        )
        return list(self.db.scalars(statement))

    def get_by_storybook_and_page(self, *, storybook_id: UUID, page_number: int) -> StoryPage | None:
        statement = select(StoryPage).where(
            StoryPage.storybook_id == storybook_id,
            StoryPage.page_number == page_number,
        )
        return self.db.scalar(statement)

    def update_fields(self, *, page: StoryPage, updates: dict[str, Any], commit: bool = True) -> StoryPage:
        for field_name, value in updates.items():
            setattr(page, field_name, value)

        self.db.add(page)
        if commit:
            self.db.commit()
            self.db.refresh(page)
        else:
            self.db.flush()
            self.db.refresh(page)
        return page
