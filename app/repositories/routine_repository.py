from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.routine import Routine


class RoutineRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, routine: Routine) -> Routine:
        self.db.add(routine)
        self.db.commit()
        self.db.refresh(routine)
        return routine

    def get_by_id_for_user(self, *, routine_id: UUID, user_id: UUID) -> Routine | None:
        statement = select(Routine).where(Routine.id == routine_id, Routine.user_id == user_id)
        return self.db.scalar(statement)

    def get_by_user_and_date(self, *, user_id: UUID, routine_date: date) -> Routine | None:
        statement = select(Routine).where(Routine.user_id == user_id, Routine.date == routine_date)
        return self.db.scalar(statement)

    def list_by_user(self, *, user_id: UUID) -> list[Routine]:
        statement = select(Routine).where(Routine.user_id == user_id).order_by(Routine.date.desc())
        return list(self.db.scalars(statement))

    def list_by_user_between_dates(
        self,
        *,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[Routine]:
        statement = (
            select(Routine)
            .where(
                Routine.user_id == user_id,
                Routine.date >= start_date,
                Routine.date <= end_date,
            )
            .order_by(Routine.date.asc())
        )
        return list(self.db.scalars(statement))

    def update_fields(self, *, routine: Routine, updates: dict[str, object]) -> Routine:
        for field_name, value in updates.items():
            setattr(routine, field_name, value)

        self.db.add(routine)
        self.db.commit()
        self.db.refresh(routine)
        return routine

    def delete(self, *, routine: Routine) -> None:
        self.db.delete(routine)
        self.db.commit()