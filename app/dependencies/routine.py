from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.repositories.routine_macro_log_repository import RoutineMacroLogRepository
from app.repositories.routine_repository import RoutineRepository
from app.services.routine_service import RoutineService


def get_routine_service(db: Session = Depends(get_db_session)) -> RoutineService:
    return RoutineService(
        routine_repository=RoutineRepository(db),
        routine_macro_log_repository=RoutineMacroLogRepository(db),
    )