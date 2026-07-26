from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.daily_goal import DailyGoalCompletion


class DailyGoalCompletionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_client_between_dates(
        self,
        *,
        client_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[DailyGoalCompletion]:
        statement = select(DailyGoalCompletion).where(
            DailyGoalCompletion.client_id == client_id,
            DailyGoalCompletion.goal_date >= start_date,
            DailyGoalCompletion.goal_date <= end_date,
        )
        return list(self.db.scalars(statement))

