from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.repositories.user_repository import UserRepository
from app.services.profile_service import ProfileService


def get_profile_service(db: Session = Depends(get_db_session)) -> ProfileService:
    return ProfileService(UserRepository(db))