from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.repositories.user_repository import UserRepository
from app.services.onboarding_service import OnboardingService


def get_onboarding_service(db: Session = Depends(get_db_session)) -> OnboardingService:
    return OnboardingService(UserRepository(db))
