from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.repositories.notification_repository import NotificationRepository
from app.services.notification_service import NotificationService


def get_notification_service(db: Session = Depends(get_db_session)) -> NotificationService:
    return NotificationService(NotificationRepository(db))
