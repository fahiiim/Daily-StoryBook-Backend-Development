from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.repositories.user_repository import UserRepository
from app.services.storage_service import StorageService
from app.services.upload_service import UploadService


def get_storage_service() -> StorageService:
    return StorageService()


def get_upload_service(
    db: Session = Depends(get_db_session),
    storage_service: StorageService = Depends(get_storage_service),
) -> UploadService:
    return UploadService(user_repository=UserRepository(db), storage_service=storage_service)