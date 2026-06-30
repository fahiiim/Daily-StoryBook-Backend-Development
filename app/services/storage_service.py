from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.core.config import BASE_DIR, settings


class StorageServiceError(Exception):
    pass


class UnsupportedImageTypeError(StorageServiceError):
    pass


class ImageTooLargeError(StorageServiceError):
    pass


class StorageConfigurationError(StorageServiceError):
    pass


class StorageService:
    CONTENT_TYPE_TO_EXTENSION: Final[dict[str, str]] = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }

    def __init__(self) -> None:
        self.backend = settings.storage_backend.strip().lower()
        self.max_image_size_bytes = settings.upload_max_image_size_bytes
        parsed_types = [
            image_type.strip().lower()
            for image_type in settings.upload_allowed_image_types.split(",")
            if image_type.strip()
        ]
        self.allowed_image_types = set(parsed_types) or set(self.CONTENT_TYPE_TO_EXTENSION.keys())

    async def upload_image(self, *, file: UploadFile, folder: str, user_id: UUID) -> str:
        content_type = (file.content_type or "").strip().lower()
        if content_type not in self.allowed_image_types:
            raise UnsupportedImageTypeError("Unsupported image type")

        extension = self.CONTENT_TYPE_TO_EXTENSION.get(content_type)
        if extension is None:
            raise UnsupportedImageTypeError("Unsupported image type")

        file_bytes = await file.read()
        if len(file_bytes) > self.max_image_size_bytes:
            raise ImageTooLargeError("Image exceeds size limit")

        object_key = f"{folder}/{user_id}/{uuid4().hex}{extension}"
        if self.backend == "s3":
            return self._upload_to_s3(
                object_key=object_key,
                content=file_bytes,
                content_type=content_type,
            )
        return self._upload_to_local(object_key=object_key, content=file_bytes)

    def _upload_to_local(self, *, object_key: str, content: bytes) -> str:
        media_root = BASE_DIR / settings.local_storage_dir
        target_file = media_root / Path(object_key)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_bytes(content)

        media_url_prefix = settings.local_media_url_prefix.strip()
        if not media_url_prefix.startswith("/"):
            media_url_prefix = f"/{media_url_prefix}"
        media_url_prefix = media_url_prefix.rstrip("/")

        public_base_url = settings.app_public_base_url.rstrip("/")
        return f"{public_base_url}{media_url_prefix}/{object_key}"

    def _upload_to_s3(self, *, object_key: str, content: bytes, content_type: str) -> str:
        if not settings.aws_s3_bucket:
            raise StorageConfigurationError("AWS_S3_BUCKET is required for S3 storage")

        if not settings.aws_access_key_id or not settings.aws_secret_access_key:
            raise StorageConfigurationError(
                "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required for S3 storage",
            )

        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError
        except ModuleNotFoundError as exc:
            raise StorageConfigurationError("boto3 is not installed") from exc

        session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

        client = session.client(
            "s3",
            endpoint_url=settings.aws_s3_endpoint_url or None,
        )

        try:
            client.put_object(
                Bucket=settings.aws_s3_bucket,
                Key=object_key,
                Body=content,
                ContentType=content_type,
                ACL="public-read",
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageServiceError("Failed to upload image to S3") from exc

        if settings.aws_s3_public_base_url:
            return f"{settings.aws_s3_public_base_url.rstrip('/')}/{object_key}"

        if settings.aws_s3_endpoint_url:
            endpoint = settings.aws_s3_endpoint_url.rstrip("/")
            return f"{endpoint}/{settings.aws_s3_bucket}/{object_key}"

        if settings.aws_region == "us-east-1":
            return f"https://{settings.aws_s3_bucket}.s3.amazonaws.com/{object_key}"

        return f"https://{settings.aws_s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{object_key}"