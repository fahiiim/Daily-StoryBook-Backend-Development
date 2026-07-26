from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_user
from app.dependencies.weekly_summary import get_weekly_summary_service
from app.main import app
from app.models.user import User, UserRole
from app.schemas.weekly_summary import (
    DailyProgressPoint,
    WeeklyProgressAnalyticsRead,
    WeeklyProgressAverages,
    WeeklyProgressCoverage,
)


class FakeWeeklySummaryService:
    def __init__(self, *, current_user: User) -> None:
        self.current_user = current_user

    def get_current_week_analytics(self, *, current_user: User):
        _ = current_user
        week_start = date(2026, 7, 20)
        points = [
            DailyProgressPoint(
                date=week_start + timedelta(days=index),
                day=(week_start + timedelta(days=index)).strftime("%a").upper(),
                workout_score=50.0,
                meal_score=75.0,
                daily_goal_score=100.0,
                combined_score=75.0,
                workout_completed=1,
                workout_assigned=2,
                meal_components_scored=5,
                daily_goals_completed=2,
                daily_goals_assigned=2,
                workout_applicable=True,
                meal_applicable=True,
                daily_goal_applicable=True,
            )
            for index in range(7)
        ]
        return WeeklyProgressAnalyticsRead(
            user_id=self.current_user.id,
            week_start=week_start,
            week_end=date(2026, 7, 26),
            as_of_date=date(2026, 7, 26),
            as_of=datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc),
            is_partial_week=False,
            daily_points=points,
            weekly_averages=WeeklyProgressAverages(
                workout_score=50.0,
                meal_score=75.0,
                daily_goal_score=100.0,
                combined_score=75.0,
                ending_workout_completion_rate=50.0,
            ),
            coverage=WeeklyProgressCoverage(
                elapsed_days=7,
                workout_days_scored=7,
                meal_days_scored=7,
                daily_goal_days_scored=7,
                combined_days_scored=7,
                complete=True,
            ),
        )


@pytest.fixture
def current_user() -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        email="weekly.user@example.com",
        hashed_password="hashed-password",
        full_name="Weekly User",
        role=UserRole.SELF,
        is_email_verified=True,
        is_active=True,
        use_reference_image=False,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def override_current_user(current_user: User):
    app.dependency_overrides[get_current_user] = lambda: current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def override_weekly_summary_service(current_user: User):
    app.dependency_overrides[get_weekly_summary_service] = lambda: FakeWeeklySummaryService(
        current_user=current_user
    )
    yield
    app.dependency_overrides.pop(get_weekly_summary_service, None)


@pytest.mark.asyncio
async def test_get_live_weekly_progress_analytics(
    override_current_user,
    override_weekly_summary_service,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/weekly-summary")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["daily_points"]) == 7
    assert payload["daily_points"][0]["combined_score"] == 75.0
    assert payload["weekly_averages"]["combined_score"] == 75.0


def test_only_live_weekly_summary_route_is_exposed() -> None:
    app.openapi_schema = None
    paths = app.openapi()["paths"]

    assert "/weekly-summary" in paths
    assert sorted(paths["/weekly-summary"]) == ["get"]
    assert "/weekly-summary/daily-goals/today" not in paths
    assert "/weekly-summary/daily-goals/today/{goal_item_id}" not in paths
    assert "/weekly-summary/generate" not in paths
    assert "/weekly-summary/current" not in paths
    assert "/weekly-summary/history" not in paths
    assert paths["/weekly-summary"]["get"].get("parameters", []) == []


@pytest.mark.asyncio
async def test_weekly_analytics_requires_authentication(
    override_weekly_summary_service,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/weekly-summary")

    assert response.status_code == 401
