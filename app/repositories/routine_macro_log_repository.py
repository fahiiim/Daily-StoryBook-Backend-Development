from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.routine_macro_log import MacroType, RoutineMacroLog


class RoutineMacroLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, log: RoutineMacroLog, commit: bool = True) -> RoutineMacroLog:
        self.db.add(log)
        if commit:
            self.db.commit()
            self.db.refresh(log)
        else:
            self.db.flush()
            self.db.refresh(log)
        return log

    def list_by_routine_for_user(self, *, routine_id: UUID, user_id: UUID) -> list[RoutineMacroLog]:
        statement = (
            select(RoutineMacroLog)
            .where(
                RoutineMacroLog.routine_id == routine_id,
                RoutineMacroLog.user_id == user_id,
            )
            .order_by(RoutineMacroLog.logged_at.desc())
        )
        return list(self.db.scalars(statement))

    def get_by_id_for_routine_user(
        self,
        *,
        log_id: UUID,
        routine_id: UUID,
        user_id: UUID,
    ) -> RoutineMacroLog | None:
        statement = select(RoutineMacroLog).where(
            RoutineMacroLog.id == log_id,
            RoutineMacroLog.routine_id == routine_id,
            RoutineMacroLog.user_id == user_id,
        )
        return self.db.scalar(statement)

    def update_fields(
        self,
        *,
        log: RoutineMacroLog,
        updates: dict[str, object],
        commit: bool = True,
    ) -> RoutineMacroLog:
        for field_name, value in updates.items():
            setattr(log, field_name, value)

        self.db.add(log)
        if commit:
            self.db.commit()
            self.db.refresh(log)
        else:
            self.db.flush()
        return log

    def delete(self, *, log: RoutineMacroLog, commit: bool = True) -> None:
        self.db.delete(log)
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def list_by_user_and_macro_type(
        self,
        *,
        user_id: UUID,
        macro_type: MacroType,
        limit: int,
    ) -> list[RoutineMacroLog]:
        nutrient_column = {
            MacroType.PROTEIN: RoutineMacroLog.protein,
            MacroType.CARBS: RoutineMacroLog.carbs,
            MacroType.FATS: RoutineMacroLog.fat,
            MacroType.FIBER: RoutineMacroLog.fiber,
        }[macro_type]
        statement = (
            select(RoutineMacroLog)
            .where(
                RoutineMacroLog.user_id == user_id,
                nutrient_column > 0,
            )
            .order_by(RoutineMacroLog.logged_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))
