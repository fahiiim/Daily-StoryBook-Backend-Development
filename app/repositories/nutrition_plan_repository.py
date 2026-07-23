from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.coach_client import CoachClient, CoachClientStatus
from app.models.nutrition_plan import NUTRITION_PLAN_VALIDITY_DAYS, NutritionPlan


_VALIDITY_OFFSET = timedelta(days=NUTRITION_PLAN_VALIDITY_DAYS - 1)


class NutritionPlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, plan: NutritionPlan) -> NutritionPlan:
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def list_by_coach(self, *, coach_id: UUID) -> list[NutritionPlan]:
        statement = (
            select(NutritionPlan)
            .where(NutritionPlan.coach_id == coach_id)
            .order_by(NutritionPlan.date.desc(), NutritionPlan.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def list_by_client(self, *, client_id: UUID) -> list[NutritionPlan]:
        statement = (
            select(NutritionPlan)
            .where(NutritionPlan.client_id == client_id)
            .order_by(NutritionPlan.date.desc(), NutritionPlan.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def list_by_client_for_coach(
        self,
        *,
        client_id: UUID,
        coach_id: UUID,
    ) -> list[NutritionPlan]:
        statement = (
            select(NutritionPlan)
            .where(
                NutritionPlan.client_id == client_id,
                NutritionPlan.coach_id == coach_id,
            )
            .order_by(NutritionPlan.date.desc(), NutritionPlan.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def get_by_id_for_coach(self, *, plan_id: UUID, coach_id: UUID) -> NutritionPlan | None:
        statement = select(NutritionPlan).where(
            NutritionPlan.id == plan_id,
            NutritionPlan.coach_id == coach_id,
        )
        return self.db.scalar(statement)

    def get_by_id_for_client(self, *, plan_id: UUID, client_id: UUID) -> NutritionPlan | None:
        statement = select(NutritionPlan).where(
            NutritionPlan.id == plan_id,
            NutritionPlan.client_id == client_id,
        )
        return self.db.scalar(statement)

    def get_active_by_coach_client_date(
        self,
        *,
        coach_id: UUID,
        client_id: UUID,
        plan_date: date,
    ) -> NutritionPlan | None:
        statement = (
            select(NutritionPlan)
            .where(
                NutritionPlan.coach_id == coach_id,
                NutritionPlan.client_id == client_id,
                NutritionPlan.date >= plan_date - _VALIDITY_OFFSET,
                NutritionPlan.date <= plan_date,
            )
            .order_by(
                NutritionPlan.date.desc(),
                NutritionPlan.updated_at.desc(),
                NutritionPlan.created_at.desc(),
            )
        )
        return self.db.scalar(statement)

    def get_overlapping_weekly_plan(
        self,
        *,
        coach_id: UUID,
        client_id: UUID,
        plan_start: date,
        exclude_plan_id: UUID | None = None,
    ) -> NutritionPlan | None:
        statement = select(NutritionPlan).where(
            NutritionPlan.coach_id == coach_id,
            NutritionPlan.client_id == client_id,
            NutritionPlan.date >= plan_start - _VALIDITY_OFFSET,
            NutritionPlan.date <= plan_start + _VALIDITY_OFFSET,
        )
        if exclude_plan_id is not None:
            statement = statement.where(NutritionPlan.id != exclude_plan_id)
        return self.db.scalar(statement.order_by(NutritionPlan.date.asc()))

    def get_active_by_client_date(self, *, client_id: UUID, plan_date: date) -> NutritionPlan | None:
        statement = (
            select(NutritionPlan)
            .join(
                CoachClient,
                and_(
                    CoachClient.coach_id == NutritionPlan.coach_id,
                    CoachClient.client_id == NutritionPlan.client_id,
                ),
            )
            .where(
                NutritionPlan.client_id == client_id,
                NutritionPlan.date >= plan_date - _VALIDITY_OFFSET,
                NutritionPlan.date <= plan_date,
                CoachClient.status == CoachClientStatus.ACCEPTED,
            )
            .order_by(
                NutritionPlan.date.desc(),
                NutritionPlan.updated_at.desc(),
                NutritionPlan.created_at.desc(),
                NutritionPlan.id.desc(),
            )
        )
        return self.db.scalar(statement)

    def update_fields(self, *, plan: NutritionPlan, updates: dict[str, object]) -> NutritionPlan:
        for field_name, value in updates.items():
            setattr(plan, field_name, value)

        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def delete(self, *, plan: NutritionPlan) -> None:
        self.db.delete(plan)
        self.db.commit()