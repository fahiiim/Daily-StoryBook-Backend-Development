from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workout_plan import WorkoutPlan, WorkoutPlanAssignment


class WorkoutPlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_plan(self, *, plan: WorkoutPlan) -> WorkoutPlan:
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def get_plan_by_id_for_coach(self, *, plan_id: UUID, coach_id: UUID) -> WorkoutPlan | None:
        statement = select(WorkoutPlan).where(
            WorkoutPlan.id == plan_id,
            WorkoutPlan.coach_id == coach_id,
        )
        return self.db.scalar(statement)

    def list_plans_by_coach(self, *, coach_id: UUID) -> list[WorkoutPlan]:
        statement = (
            select(WorkoutPlan)
            .where(WorkoutPlan.coach_id == coach_id)
            .order_by(WorkoutPlan.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def update_plan_fields(self, *, plan: WorkoutPlan, updates: dict[str, object]) -> WorkoutPlan:
        for field_name, value in updates.items():
            setattr(plan, field_name, value)

        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def delete_plan(self, *, plan: WorkoutPlan) -> None:
        self.db.delete(plan)
        self.db.commit()

    def assignment_exists(self, *, plan_id: UUID, client_id: UUID) -> bool:
        statement = select(WorkoutPlanAssignment.id).where(
            WorkoutPlanAssignment.plan_id == plan_id,
            WorkoutPlanAssignment.client_id == client_id,
        )
        return self.db.scalar(statement) is not None

    def create_assignment(self, *, assignment: WorkoutPlanAssignment) -> WorkoutPlanAssignment:
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def list_plans_for_client(self, *, client_id: UUID) -> list[WorkoutPlan]:
        statement = (
            select(WorkoutPlan)
            .join(WorkoutPlanAssignment, WorkoutPlanAssignment.plan_id == WorkoutPlan.id)
            .where(WorkoutPlanAssignment.client_id == client_id)
            .order_by(WorkoutPlan.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def list_plans_for_client_by_coach(
        self,
        *,
        client_id: UUID,
        coach_id: UUID,
    ) -> list[WorkoutPlan]:
        statement = (
            select(WorkoutPlan)
            .join(WorkoutPlanAssignment, WorkoutPlanAssignment.plan_id == WorkoutPlan.id)
            .where(
                WorkoutPlanAssignment.client_id == client_id,
                WorkoutPlan.coach_id == coach_id,
                WorkoutPlanAssignment.assigned_by_coach_id == coach_id,
            )
            .order_by(WorkoutPlan.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def get_plan_for_client(self, *, plan_id: UUID, client_id: UUID) -> WorkoutPlan | None:
        statement = (
            select(WorkoutPlan)
            .join(WorkoutPlanAssignment, WorkoutPlanAssignment.plan_id == WorkoutPlan.id)
            .where(
                WorkoutPlan.id == plan_id,
                WorkoutPlanAssignment.client_id == client_id,
            )
        )
        return self.db.scalar(statement)