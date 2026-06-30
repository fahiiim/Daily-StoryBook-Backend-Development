from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.ai import get_ai_service
from app.dependencies.auth import get_current_user
from app.main import app
from app.models.user import User, UserRole
from app.services.ai_service import AIServiceTimeoutError


class FakeAIService:
    async def generate_storybook(self, *, payload, selfie):
        _ = payload
        _ = selfie
        return {"success": True, "book_id": "book-1", "total_pages": 10}

    async def get_storybook(self, *, book_id: str):
        return {"success": True, "book_id": book_id, "pages": []}

    async def get_storybook_page(self, *, book_id: str, page_number: int):
        return {
            "success": True,
            "book_id": book_id,
            "page_number": page_number,
            "title": "Page title",
        }

    async def regenerate_page(self, *, book_id: str, page_number: int, payload):
        _ = payload
        return {"success": True, "book_id": book_id, "page_number": page_number}

    async def regenerate_image(self, *, book_id: str, page_number: int, payload):
        _ = payload
        return {
            "success": True,
            "book_id": book_id,
            "page_number": page_number,
            "image_url": f"/api/v1/storybook/{book_id}/page/{page_number}/image",
        }

    async def rebuild_pdf(self, *, book_id: str):
        return {"success": True, "book_id": book_id, "pdf_url": f"/api/v1/storybook/{book_id}/pdf"}


class TimeoutAIService(FakeAIService):
    async def get_storybook(self, *, book_id: str):
        _ = book_id
        raise AIServiceTimeoutError("AI service request timed out")


@pytest.fixture
def current_user() -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        email="storybook.user@example.com",
        hashed_password="hashed-password",
        full_name="Storybook User",
        age=30,
        gender="male",
        occupation="Engineer",
        fitness_goal="General Fitness",
        profile_image=None,
        reference_image=None,
        role=UserRole.SELF,
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
def override_ai_service():
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()
    yield
    app.dependency_overrides.pop(get_ai_service, None)


@pytest.mark.asyncio
async def test_generate_storybook(override_current_user, override_ai_service) -> None:
    form_data = {
        "name": "Alex",
        "age": "29",
        "gender": "Male",
        "fitness_goal": "Weight Loss",
        "wake_up_time": "06:30",
        "bed_time": "22:30",
        "image_style": "ghibli_animation",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/storybook/generate",
            data=form_data,
            files={"selfie": ("selfie.png", b"fake-image", "image/png")},
        )

    assert response.status_code == 200
    assert response.json()["book_id"] == "book-1"


@pytest.mark.asyncio
async def test_get_storybook(override_current_user, override_ai_service) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/storybook/book-123")

    assert response.status_code == 200
    assert response.json()["book_id"] == "book-123"


@pytest.mark.asyncio
async def test_regenerate_page(override_current_user, override_ai_service) -> None:
    payload = {"title": "New title"}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/storybook/book-1/page/2/regenerate", json=payload)

    assert response.status_code == 200
    assert response.json()["page_number"] == 2


@pytest.mark.asyncio
async def test_get_storybook_page_compact_route(override_current_user, override_ai_service) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/storybook/page/3", params={"book_id": "book-xyz"})

    assert response.status_code == 200
    assert response.json()["book_id"] == "book-xyz"
    assert response.json()["page_number"] == 3


@pytest.mark.asyncio
async def test_regenerate_page_compact_route(override_current_user, override_ai_service) -> None:
    payload = {
        "book_id": "book-1",
        "page_id": 4,
        "title": "Refined title",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/storybook/page/regenerate", json=payload)

    assert response.status_code == 200
    assert response.json()["page_number"] == 4


@pytest.mark.asyncio
async def test_regenerate_image(override_current_user, override_ai_service) -> None:
    payload = {"image_prompt": "A colorful fitness scene", "image_style": "ghibli_animation"}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/storybook/book-1/page/2/image", json=payload)

    assert response.status_code == 200
    assert "image_url" in response.json()


@pytest.mark.asyncio
async def test_regenerate_image_compact_route(override_current_user, override_ai_service) -> None:
    payload = {
        "book_id": "book-1",
        "page_id": 5,
        "image_prompt": "A bright gym illustration",
        "image_style": "ghibli_animation",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/storybook/image/regenerate", json=payload)

    assert response.status_code == 200
    assert response.json()["page_number"] == 5


@pytest.mark.asyncio
async def test_rebuild_pdf(override_current_user, override_ai_service) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/storybook/book-1/rebuild-pdf")

    assert response.status_code == 200
    assert response.json()["pdf_url"] == "/api/v1/storybook/book-1/pdf"


@pytest.mark.asyncio
async def test_ai_timeout_maps_to_gateway_timeout(override_current_user) -> None:
    app.dependency_overrides[get_ai_service] = lambda: TimeoutAIService()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/storybook/book-1")
    finally:
        app.dependency_overrides.pop(get_ai_service, None)

    assert response.status_code == 504