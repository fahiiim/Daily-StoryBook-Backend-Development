from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.repositories.admin_repository import AdminRepository
from app.repositories.user_repository import UserRepository
from app.services.admin_service import AdminService


def get_admin_service(db: Session = Depends(get_db_session)) -> AdminService:
    return AdminService(
        admin_repository=AdminRepository(db),
        user_repository=UserRepository(db),
    )
