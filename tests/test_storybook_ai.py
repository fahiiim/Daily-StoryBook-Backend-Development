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
                story="Page one story",
                image_url="/images/1.png",
                is_edited=False,
                created_at=now,
                updated_at=now,
            )
        }

    async def create_storybook_generation(self, *, current_user: User, **kwargs) -> StorybookGenerationJob:
        _ = current_user
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
        role=UserRole.SELF,
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
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/storybook/generate",
            data={"wake_up_time": "06:30", "bed_time": "22:00"},
            files={"selfie": ("selfie.png", b"fake-image", "image/png")},
        )

    assert response.status_code == 202
    assert "storybook_id" in response.json()


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
