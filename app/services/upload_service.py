from uuid import UUID

from fastapi import UploadFile

from app.repositories.user_repository import UserRepository
from app.services.storage_service import (
    ImageTooLargeError,
    StorageConfigurationError,
    StorageService,
    StorageServiceError,
    UnsupportedImageTypeError,
)


class UploadServiceError(Exception):
    pass


class UploadUserNotFoundError(UploadServiceError):
    pass


class UploadService:
    def __init__(self, user_repository: UserRepository, storage_service: StorageService) -> None:
        self.user_repository = user_repository
        self.storage_service = storage_service

    async def upload_profile_image(self, *, user_id: UUID, file: UploadFile) -> str:
        return await self._upload_and_persist(
            user_id=user_id,
            file=file,
            folder="profile",
            user_field="profile_image",
        )

    async def upload_reference_image(self, *, user_id: UUID, file: UploadFile) -> str:
        return await self._upload_and_persist(
            user_id=user_id,
            file=file,
            folder="reference",
            user_field="reference_image",
        )

    async def _upload_and_persist(
        self,
        *,
        user_id: UUID,
        file: UploadFile,
        folder: str,
        user_field: str,
    ) -> str:
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise UploadUserNotFoundError("User not found")

        url = await self.storage_service.upload_image(file=file, folder=folder, user_id=user_id)
        self.user_repository.update_fields(user=user, updates={user_field: url})
        return url


__all__ = [
    "ImageTooLargeError",
    "StorageConfigurationError",
    "StorageServiceError",
    "UnsupportedImageTypeError",
    "UploadService",
    "UploadServiceError",
    "UploadUserNotFoundError",
]