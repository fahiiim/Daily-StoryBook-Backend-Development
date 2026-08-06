from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_user
from app.dependencies.storybook import get_storybook_service
from app.main import app
from app.models.storybook import Storybook, StorybookStatus, StoryPage
from app.models.user import User, UserRole
from app.schemas.ai import RegeneratePageRequest
from app.services.ai_service import AIServiceTimeoutError
from app.services.storybook_service import (
    StorybookGenerationJob,
    StorybookAccessError,
    StorybookNotFoundError,
    StorybookService,
    StoryPageNotFoundError,
)


class FakeStorybookService:
    def __init__(self, *, current_user: User) -> None:
        now = datetime.now(tz=timezone.utc)
        self.current_user = current_user
        self.storybook = Storybook(
            id=uuid4(),
            user_id=current_user.id,
            ai_book_id="ai-book-1",
            date=date(2026, 7, 5),
            status=StorybookStatus.COMPLETED,
            pdf_url="/storybook/pdf/ai-book-1",
            generated_at=now,
            created_at=now,
            updated_at=now,
        )
        self.pages = {
            1: StoryPage(
                id=uuid4(),
                storybook_id=self.storybook.id,
                page_number=1,
                title="Morning Momentum",
                story="Page one story",
                image_url="/images/1.png",
                is_edited=False,
                created_at=now,
                updated_at=now,
            )
        }

    async def create_storybook_generation(self, **kwargs) -> StorybookGenerationJob:
        _ = kwargs
        return StorybookGenerationJob(
            storybook_id=self.storybook.id,
            payload=None,
            selfie_bytes=b"",
            selfie_filename="selfie.png",
            selfie_content_type="image/png",
        )

    async def process_storybook_generation(self, *, job: StorybookGenerationJob) -> None:
        _ = job
        return None

    def get_storybook(self, *, current_user: User, storybook_id: UUID):
        if storybook_id != self.storybook.id:
            raise StorybookNotFoundError("Storybook not found")
        if current_user.id != self.storybook.user_id:
            raise StorybookAccessError("Access to storybook is forbidden")
        return self.storybook, list(self.pages.values())

    def get_latest_storybooks(self, *, current_user: User):
        if current_user.id != self.storybook.user_id:
            raise StorybookAccessError("Access to storybook is forbidden")
        return [(self.storybook, list(self.pages.values()))]

    def get_coach_client_storybook_statuses(self, *, current_coach: User):
        if current_coach.role != UserRole.COACH:
            raise StorybookAccessError("Coach role required")
        return [
            {
                "client_id": self.current_user.id,
                "profile_name": self.current_user.full_name,
                "profile_image": self.current_user.profile_image,
                "storybook_id": self.storybook.id,
                "storybook_status": self.storybook.status,
                "valid_from": self.storybook.date,
                "valid_until": self.storybook.date,
                "is_valid_now": True,
                "needs_regeneration": False,
            }
        ]

    def get_storybook_page(self, *, current_user: User, storybook_id: UUID, page_number: int):
        if storybook_id != self.storybook.id:
            raise StorybookNotFoundError("Storybook not found")
        if current_user.id != self.storybook.user_id:
            raise StorybookAccessError("Access to storybook is forbidden")
        if page_number not in self.pages:
            raise StoryPageNotFoundError("Storybook page not found")
        return self.pages[page_number]

    def update_story_page(self, *, current_user: User, storybook_id: UUID, page_number: int, story: str):
        page = self.get_storybook_page(
            current_user=current_user,
            storybook_id=storybook_id,
            page_number=page_number,
        )
        page.story = story
        page.is_edited = True
        return page

    async def regenerate_story(self, *, current_user: User, storybook_id: UUID, page_number: int, payload):
        _ = payload
        page = self.get_storybook_page(
            current_user=current_user,
            storybook_id=storybook_id,
            page_number=page_number,
        )
        page.story = "Regenerated story"
        page.is_edited = True
        return page

    async def regenerate_image(self, *, current_user: User, storybook_id: UUID, page_number: int, payload):
        _ = payload
        page = self.get_storybook_page(
            current_user=current_user,
            storybook_id=storybook_id,
            page_number=page_number,
        )
        page.image_url = "/images/regenerated.png"
        return page

    async def regenerate_story_and_image(
        self,
        *,
        current_user: User,
        storybook_id: UUID,
        page_number: int,
        payload,
    ):
        _ = payload
        page = self.get_storybook_page(
            current_user=current_user,
            storybook_id=storybook_id,
            page_number=page_number,
        )
        page.story = "Regenerated story"
        page.image_url = "/images/regenerated.png"
        page.is_edited = True
        return page

    def get_pdf_url(self, *, current_user: User, storybook_id: UUID) -> str:
        _ = current_user
        if storybook_id != self.storybook.id:
            raise StorybookNotFoundError("Storybook not found")
        return self.storybook.pdf_url or ""

    def get_storybook_status(self, *, current_user: User, storybook_id: UUID):
        _ = current_user
        if storybook_id != self.storybook.id:
            raise StorybookNotFoundError("Storybook not found")
        return self.storybook.status


class TimeoutStorybookService(FakeStorybookService):
    async def regenerate_story(self, *, current_user: User, storybook_id: UUID, page_number: int, payload):
        _ = current_user
        _ = storybook_id
        _ = page_number
        _ = payload
        raise AIServiceTimeoutError("AI service request timed out")


@pytest.fixture
def current_user() -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        email="storybook.user@example.com",
        hashed_password="hashed-password",
        full_name="Storybook User",
        age=None,
        date_of_birth=date(1994, 7, 10),
        gender="male",
        occupation="Engineer",
        fitness_goal="General Fitness",
        bio=None,
        profile_image=None,
        reference_image=None,
        use_reference_image=False,
        role=UserRole.COACH,
        is_email_verified=False,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def override_current_user(current_user: User):
    app.dependency_overrides[get_current_user] = lambda: current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def override_storybook_service(current_user: User):
    app.dependency_overrides[get_storybook_service] = lambda: FakeStorybookService(
        current_user=current_user,
    )
    yield
    app.dependency_overrides.pop(get_storybook_service, None)


@pytest.mark.asyncio
async def test_generate_storybook(override_current_user, override_storybook_service) -> None:
    client_id = str(uuid4())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/storybook/generate",
            data={"client_id": client_id, "wake_up_time": "06:30", "bed_time": "22:00"},
            files={"selfie": ("selfie.png", b"fake-image", "image/png")},
        )

    assert response.status_code == 202
    assert "storybook_id" in response.json()


@pytest.mark.asyncio
async def test_execute_storybook_generation_without_manual_context_or_selfie(
    override_current_user,
    override_storybook_service,
) -> None:
    client_id = str(uuid4())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/storybook/generate/execute",
            data={"client_id": client_id},
        )

    assert response.status_code == 202
    assert "storybook_id" in response.json()


@pytest.mark.asyncio
async def test_execute_storybook_generation_accepts_context_override(
    override_current_user,
    override_storybook_service,
) -> None:
    client_id = str(uuid4())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/storybook/generate/execute",
            data={"client_id": client_id, "context_json": '{"source":"manual"}'},
        )

    assert response.status_code == 202
    assert "storybook_id" in response.json()


@pytest.mark.asyncio
async def test_execute_storybook_generation_ignores_swagger_placeholder_context(
    override_current_user,
    override_storybook_service,
) -> None:
    client_id = str(uuid4())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/storybook/generate/execute",
            data={"client_id": client_id, "context_json": "string"},
        )

    assert response.status_code == 202
    assert "storybook_id" in response.json()


@pytest.mark.asyncio
async def test_execute_storybook_generation_rejects_invalid_context_json(
    override_current_user,
    override_storybook_service,
) -> None:
    client_id = str(uuid4())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/storybook/generate/execute",
            data={"client_id": client_id, "context_json": "not-json"},
        )

    assert response.status_code == 422
    assert "context_json must be a valid JSON object" in response.json()["detail"]


@pytest.mark.asyncio
async def test_generate_storybook_forbidden_for_non_coach(override_storybook_service) -> None:
    now = datetime.now(tz=timezone.utc)
    self_user = User(
        id=uuid4(),
        email="self.user@example.com",
        hashed_password="hashed-password",
        full_name="Self User",
        role=UserRole.SELF,
        use_reference_image=False,
        is_email_verified=True,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    app.dependency_overrides[get_current_user] = lambda: self_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/storybook/generate/execute",
            data={"client_id": str(uuid4())},
        )

    assert response.status_code == 403
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_get_storybook(override_current_user, override_storybook_service, current_user: User) -> None:
    service = FakeStorybookService(current_user=current_user)
    app.dependency_overrides[get_storybook_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"/storybook/{service.storybook.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(service.storybook.id)
    app.dependency_overrides.pop(get_storybook_service, None)


@pytest.mark.asyncio
async def test_get_latest_storybooks(override_current_user, override_storybook_service, current_user: User) -> None:
    service = FakeStorybookService(current_user=current_user)
    app.dependency_overrides[get_storybook_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/storybook")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["id"] == str(service.storybook.id)
    assert payload[0]["pages"][0]["title"] == "Morning Momentum"
    app.dependency_overrides.pop(get_storybook_service, None)


@pytest.mark.asyncio
async def test_get_coach_clients_storybook_status(
    override_current_user,
    override_storybook_service,
    current_user: User,
) -> None:
    service = FakeStorybookService(current_user=current_user)
    app.dependency_overrides[get_storybook_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/storybook/coach/clients/status")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["profile_name"] == current_user.full_name
    assert "profile_image" in payload[0]
    assert payload[0]["storybook_status"] == "COMPLETED"
    app.dependency_overrides.pop(get_storybook_service, None)


@pytest.mark.asyncio
async def test_get_storybook_page(override_current_user, override_storybook_service, current_user: User) -> None:
    service = FakeStorybookService(current_user=current_user)
    app.dependency_overrides[get_storybook_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"/storybook/{service.storybook.id}/page/1")

    assert response.status_code == 200
    assert response.json()["page_number"] == 1
    app.dependency_overrides.pop(get_storybook_service, None)


@pytest.mark.asyncio
async def test_update_storybook_page(override_current_user, override_storybook_service, current_user: User) -> None:
    service = FakeStorybookService(current_user=current_user)
    app.dependency_overrides[get_storybook_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.put(
            f"/storybook/{service.storybook.id}/page/1",
            json={"story": "Updated story"},
        )

    assert response.status_code == 200
    assert response.json()["story"] == "Updated story"
    app.dependency_overrides.pop(get_storybook_service, None)


@pytest.mark.asyncio
async def test_regenerate_story_handles_ai_timeout(override_current_user, current_user: User) -> None:
    app.dependency_overrides[get_storybook_service] = lambda: TimeoutStorybookService(
        current_user=current_user,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            f"/storybook/{uuid4()}/page/1/regenerate-story",
            json=RegeneratePageRequest(story_text="Refresh").model_dump(),
        )

    assert response.status_code == 504
    app.dependency_overrides.pop(get_storybook_service, None)


@pytest.mark.asyncio
async def test_make_upload_file_sets_content_type_and_payload() -> None:
    upload = StorybookService._make_upload_file(
        file_bytes=b"image-bytes",
        filename="selfie.png",
        content_type="image/png",
    )

    assert upload.content_type == "image/png"
    assert await upload.read() == b"image-bytes"


def test_ai_context_enum_normalization_helpers() -> None:
    assert StorybookService._normalize_ai_fitness_goal("GENERAL_FITNESS") == "General Fitness"
    assert StorybookService._normalize_ai_gender("male") == "Male"
    assert StorybookService._normalize_ai_gender("UNSPECIFIED") == "Prefer Not To Say"
    assert StorybookService._normalize_ai_meal_type("breakfast") == "BREAKFAST"


def test_decode_base64_image_supports_raw_png_payload() -> None:
    # 1x1 transparent PNG
    png_base64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
        "/w8AAn8B9pU6NwAAAABJRU5ErkJggg=="
    )
    decoded = StorybookService._decode_base64_image(png_base64)

    assert decoded is not None
    file_bytes, filename, content_type = decoded
    assert content_type == "image/png"
    assert filename.endswith(".png")
    assert file_bytes.startswith(b"\x89PNG")


def test_decode_base64_image_detects_gif_content_type() -> None:
    gif_base64 = "R0lGODlhAQABAIABAP///wAAACwAAAAAAQABAAACAkQBADs="
    decoded = StorybookService._decode_base64_image(gif_base64)

    assert decoded is not None
    _file_bytes, _filename, content_type = decoded
    assert content_type == "image/gif"


def test_normalize_ai_asset_url_from_relative_path() -> None:
    normalized = StorybookService._normalize_ai_asset_url("/api/v1/storybook/book-1/pdf")
    assert normalized is not None
    assert normalized.startswith("http://")
    assert normalized.endswith("/api/v1/storybook/book-1/pdf")


def test_extract_cover_image_url_falls_back_to_cover_image_route() -> None:
    fallback = StorybookService._extract_cover_image_url({}, ai_book_id="book-123")
    assert fallback == "/api/v1/storybook/book-123/cover/image"
