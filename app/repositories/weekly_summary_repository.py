from datetime import date
from uuid import UUID
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.weekly_summary import WeeklySummary


class WeeklySummaryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, summary: WeeklySummary, commit: bool = True) -> WeeklySummary:
        self.db.add(summary)
        if commit:
            self.db.commit()
            self.db.refresh(summary)
        else:
            self.db.flush()
            self.db.refresh(summary)
        return summary

    def get_by_user_and_week_start(
        self,
        *,
        user_id: UUID,
        week_start: date,
    ) -> WeeklySummary | None:
        statement = select(WeeklySummary).where(
            WeeklySummary.user_id == user_id,
            WeeklySummary.week_start == week_start,
        )
        return self.db.scalar(statement)

    def list_by_user(self, *, user_id: UUID) -> list[WeeklySummary]:
        statement = (
            select(WeeklySummary)
            .where(WeeklySummary.user_id == user_id)
            .order_by(WeeklySummary.week_start.desc())
        )
        return list(self.db.scalars(statement))

    def update_fields(
        self,
        *,
        summary: WeeklySummary,
        updates: dict[str, Any],
        commit: bool = True,
    ) -> WeeklySummary:
        for field_name, value in updates.items():
            setattr(summary, field_name, value)

        self.db.add(summary)
        if commit:
            self.db.commit()
            self.db.refresh(summary)
        else:
            self.db.flush()
            self.db.refresh(summary)
        return summary
