from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.user_repository import UserRepository
from app.services.coach_client_service import CoachClientService


def get_coach_client_service(db: Session = Depends(get_db_session)) -> CoachClientService:
    return CoachClientService(
        user_repository=UserRepository(db),
        coach_client_repository=CoachClientRepository(db),
    )