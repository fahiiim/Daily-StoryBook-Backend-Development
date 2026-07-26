from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workout_plan import WorkoutPlanCompletion


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
    ) -> WorkoutPlanCompletion:
        completion = self.get_by_item_for_client(
            nutrition_plan_id=nutrition_plan_id,
            client_id=client_id,
            workout_item_id=workout_item_id,
        )
        if completion is None:
            completion = WorkoutPlanCompletion(
                nutrition_plan_id=nutrition_plan_id,
                client_id=client_id,
                workout_item_id=workout_item_id,
            )

        completion.is_completed = completed
        completion.completed_at = completed_at
        self.db.add(completion)
        self.db.commit()
        self.db.refresh(completion)
        return completion
