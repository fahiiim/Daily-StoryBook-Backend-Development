from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.repositories.routine_repository import RoutineRepository
from app.services.weekly_summary_service import WeeklySummaryService


def get_weekly_summary_service(db: Session = Depends(get_db_session)) -> WeeklySummaryService:
    return WeeklySummaryService(RoutineRepository(db))