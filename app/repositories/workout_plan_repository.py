from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workout_plan import WorkoutPlanCompletion, WorkoutPlanCompletionEvent


class WorkoutPlanCompletionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_plan_for_client(
        self,
        *,
        nutrition_plan_id: UUID,
        client_id: UUID,
    ) -> list[WorkoutPlanCompletion]:
        statement = select(WorkoutPlanCompletion).where(
            WorkoutPlanCompletion.nutrition_plan_id == nutrition_plan_id,
            WorkoutPlanCompletion.client_id == client_id,
        )
        return list(self.db.scalars(statement))

    def get_by_item_for_client(
        self,
        *,
        nutrition_plan_id: UUID,
        client_id: UUID,
        workout_item_id: UUID,
    ) -> WorkoutPlanCompletion | None:
        statement = select(WorkoutPlanCompletion).where(
            WorkoutPlanCompletion.nutrition_plan_id == nutrition_plan_id,
            WorkoutPlanCompletion.client_id == client_id,
            WorkoutPlanCompletion.workout_item_id == workout_item_id,
        )
        return self.db.scalar(statement)

    def set_completion(
        self,
        *,
        nutrition_plan_id: UUID,
        client_id: UUID,
        workout_item_id: UUID,
        completed: bool,
        completed_at: datetime | None,
        effective_date: date,
    ) -> WorkoutPlanCompletion:
        completion = self.get_by_item_for_client(
            nutrition_plan_id=nutrition_plan_id,
            client_id=client_id,
            workout_item_id=workout_item_id,
        )
        state_changed = completion is None or completion.is_completed != completed
        if completion is None:
            completion = WorkoutPlanCompletion(
                nutrition_plan_id=nutrition_plan_id,
                client_id=client_id,
                workout_item_id=workout_item_id,
            )

        completion.is_completed = completed
        completion.completed_at = completed_at
        self.db.add(completion)
        if state_changed:
            self.db.add(
                WorkoutPlanCompletionEvent(
                    nutrition_plan_id=nutrition_plan_id,
                    client_id=client_id,
                    workout_item_id=workout_item_id,
                    completed=completed,
                    effective_date=effective_date,
                    occurred_at=completed_at or datetime.now(tz=timezone.utc),
                )
            )
        try:
            self.db.commit()
            self.db.refresh(completion)
        except Exception:
            self.db.rollback()
            raise
        return completion

    def list_events_for_client_through_date(
        self,
        *,
        client_id: UUID,
        end_date: date,
    ) -> list[WorkoutPlanCompletionEvent]:
        statement = (
            select(WorkoutPlanCompletionEvent)
            .where(
                WorkoutPlanCompletionEvent.client_id == client_id,
                WorkoutPlanCompletionEvent.effective_date <= end_date,
            )
            .order_by(
                WorkoutPlanCompletionEvent.effective_date.asc(),
                WorkoutPlanCompletionEvent.occurred_at.asc(),
                WorkoutPlanCompletionEvent.id.asc(),
            )
        )
        return list(self.db.scalars(statement))
