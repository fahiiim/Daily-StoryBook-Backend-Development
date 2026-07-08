from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_user
from app.dependencies.weekly_summary import get_weekly_summary_service
from app.main import app
from app.models.user import User, UserRole


class FakeWeeklySummaryService:
    def get_weekly_summary(self, *, current_user: User, week_start: date | None = None):
        _ = current_user
        _ = week_start
        return {
            "week_start": "2026-06-29",
            "week_end": "2026-07-05",
            "total_routines": 5,
            "completed_routines": 4,
            "completion_rate": 80.0,
            "average_water_intake": 2.4,
            "average_sleep": 7.1,
            "workout_entries": 5,
            "meal_entries": 4,
            "notes_entries": 3,
        }


@pytest.fixture
def current_user() -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        username="weekly_user",
        email="weekly.user@example.com",
        hashed_password="hashed-password",
        full_name="Weekly User",
        age=None,
        date_of_birth=date(1993, 8, 8),
        gender="female",
        occupation="Analyst",
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
def override_weekly_summary_service():
    app.dependency_overrides[get_weekly_summary_service] = lambda: FakeWeeklySummaryService()
    yield
    app.dependency_overrides.pop(get_weekly_summary_service, None)


@pytest.mark.asyncio
async def test_get_weekly_summary(override_current_user, override_weekly_summary_service) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/weekly-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_routines"] == 5
    assert payload["completion_rate"] == 80.0


@pytest.mark.asyncio
async def test_get_weekly_summary_with_query_date(
    override_current_user,
    override_weekly_summary_service,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/weekly-summary", params={"week_start": "2026-06-29"})

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_weekly_summary_requires_authentication(override_weekly_summary_service) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/weekly-summary")

    assert response.status_code == 401
