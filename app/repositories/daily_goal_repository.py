from datetime import date, datetime
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

    def list_by_plan_client_date(
        self,
        *,
        nutrition_plan_id: UUID,
        client_id: UUID,
        goal_date: date,
    ) -> list[DailyGoalCompletion]:
        statement = select(DailyGoalCompletion).where(
            DailyGoalCompletion.nutrition_plan_id == nutrition_plan_id,
            DailyGoalCompletion.client_id == client_id,
            DailyGoalCompletion.goal_date == goal_date,
        )
        return list(self.db.scalars(statement))

    def set_completion(
        self,
        *,
        nutrition_plan_id: UUID,
        client_id: UUID,
        goal_item_id: UUID,
        goal_date: date,
        completed: bool,
        completed_at: datetime | None,
    ) -> DailyGoalCompletion:
        statement = select(DailyGoalCompletion).where(
            DailyGoalCompletion.nutrition_plan_id == nutrition_plan_id,
            DailyGoalCompletion.client_id == client_id,
            DailyGoalCompletion.goal_item_id == goal_item_id,
            DailyGoalCompletion.goal_date == goal_date,
        )
        completion = self.db.scalar(statement)
        if completion is None:
            completion = DailyGoalCompletion(
                nutrition_plan_id=nutrition_plan_id,
                client_id=client_id,
                goal_item_id=goal_item_id,
                goal_date=goal_date,
            )

        completion.is_completed = completed
        completion.completed_at = completed_at
        self.db.add(completion)
        try:
            self.db.commit()
            self.db.refresh(completion)
        except Exception:
            self.db.rollback()
            raise
        return completion
