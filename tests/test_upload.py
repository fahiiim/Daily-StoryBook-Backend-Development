from datetime import date
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_user
from app.dependencies.upload import get_upload_service
from app.main import app
from app.models.user import User, UserRole
from app.services.storage_service import ImageTooLargeError, UnsupportedImageTypeError


class FakeUploadService:
    async def upload_profile_image(self, *, user_id, file):
        return await self._upload(file=file, folder="profile")

    async def upload_reference_image(self, *, user_id, file):
        return await self._upload(file=file, folder="reference")

    async def _upload(self, *, file, folder: str) -> str:
        content_type = (file.content_type or "").lower()
        if content_type not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
            raise UnsupportedImageTypeError("Unsupported image type")

        content = await file.read()
        if len(content) > 1024:
            raise ImageTooLargeError("Image exceeds size limit")

        return f"http://testserver/media/{folder}/{uuid4().hex}.png"


@pytest.fixture
def authenticated_user() -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        username="upload_user",
        email="upload.user@example.com",
        hashed_password="hashed-password",
        full_name="Upload User",
        age=None,
        date_of_birth=date(1997, 5, 5),
        gender="male",
        occupation="Coach",
        fitness_goal="Increase endurance",
        bio=None,
        profile_image=None,
        reference_image=None,
        use_reference_image=False,
        role=UserRole.SELF,
        is_email_verified=False,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def fake_upload_service() -> FakeUploadService:
    return FakeUploadService()


@pytest.fixture
def override_upload_service(fake_upload_service: FakeUploadService):
    app.dependency_overrides[get_upload_service] = lambda: fake_upload_service
    yield
    app.dependency_overrides.pop(get_upload_service, None)


@pytest.fixture
def override_current_user(authenticated_user: User):
    app.dependency_overrides[get_current_user] = lambda: authenticated_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_upload_profile_success(override_upload_service, override_current_user) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/upload/profile",
            files={"file": ("profile.png", b"small-image", "image/png")},
        )

    assert response.status_code == 200
    assert response.json()["url"].startswith("http://testserver/media/profile/")


@pytest.mark.asyncio
async def test_upload_reference_success(override_upload_service, override_current_user) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/upload/reference",
            files={"file": ("reference.jpg", b"small-image", "image/jpeg")},
        )

    assert response.status_code == 200
    assert response.json()["url"].startswith("http://testserver/media/reference/")


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_type(override_upload_service, override_current_user) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/upload/profile",
            files={"file": ("document.txt", b"not-an-image", "text/plain")},
        )

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_upload_rejects_large_file(override_upload_service, override_current_user) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/upload/reference",
            files={"file": ("large.png", b"a" * 2048, "image/png")},
        )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_upload_requires_authentication(override_upload_service) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/upload/profile",
            files={"file": ("profile.png", b"small-image", "image/png")},
        )

    assert response.status_code == 401