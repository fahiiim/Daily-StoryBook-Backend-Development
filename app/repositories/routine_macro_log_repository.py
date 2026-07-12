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

    def list_by_user_and_macro_type(
        self,
        *,
        user_id: UUID,
        macro_type: MacroType,
        limit: int,
    ) -> list[RoutineMacroLog]:
        statement = (
            select(RoutineMacroLog)
            .where(
                RoutineMacroLog.user_id == user_id,
                RoutineMacroLog.macro_type == macro_type,
            )
            .order_by(RoutineMacroLog.logged_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))
