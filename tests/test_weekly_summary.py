from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_user
from app.dependencies.weekly_summary import get_weekly_summary_service
from app.main import app
from app.models.user import User, UserRole
from app.schemas.weekly_summary import (
    DailyGoalItemRead,
    DailyGoalsTodayRead,
    DailyProgressPoint,
    WeeklyProgressAnalyticsRead,
    WeeklyProgressAverages,
    WeeklyProgressCoverage,
)


class FakeWeeklySummaryService:
    def __init__(self, *, current_user: User) -> None:
        self.current_user = current_user
        self.plan_id = uuid4()
        self.goal_id = uuid4()
        self.goal_completed = False

    def get_current_week_analytics(self, *, current_user: User, user_id=None):
        _ = current_user
        _ = user_id
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

    def get_today_daily_goals(self, *, current_user: User):
        _ = current_user
        item = DailyGoalItemRead(
            id=self.goal_id,
            position=0,
            instruction="Drink enough water",
            completed=self.goal_completed,
            completed_at=(
                datetime(2026, 7, 26, 10, 0, tzinfo=timezone.utc)
                if self.goal_completed
                else None
            ),
        )
        return DailyGoalsTodayRead(
            nutrition_plan_id=self.plan_id,
            goal_date=date(2026, 7, 26),
            items=[item],
            completed_count=1 if self.goal_completed else 0,
            total_count=1,
            completion_rate=100.0 if self.goal_completed else 0.0,
            all_completed=self.goal_completed,
        )

    def update_today_daily_goal(
        self,
        *,
        current_user: User,
        goal_item_id,
        completed: bool,
    ):
        _ = current_user
        assert goal_item_id == self.goal_id
        self.goal_completed = completed
        return self.get_today_daily_goals(current_user=current_user).items[0]


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
def fake_weekly_summary_service(current_user: User) -> FakeWeeklySummaryService:
    return FakeWeeklySummaryService(current_user=current_user)


@pytest.fixture
def override_current_user(current_user: User):
    app.dependency_overrides[get_current_user] = lambda: current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def override_weekly_summary_service(fake_weekly_summary_service: FakeWeeklySummaryService):
    app.dependency_overrides[get_weekly_summary_service] = lambda: fake_weekly_summary_service
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
    assert payload["weekly_averages"] == {
        "workout_score": 50.0,
        "meal_score": 75.0,
        "daily_goal_score": 100.0,
        "combined_score": 75.0,
        "ending_workout_completion_rate": 50.0,
    }
    assert payload["coverage"]["complete"] is True


@pytest.mark.asyncio
async def test_self_gets_and_completes_today_daily_goal(
    override_current_user,
    override_weekly_summary_service,
    fake_weekly_summary_service: FakeWeeklySummaryService,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        initial = await client.get("/weekly-summary/daily-goals/today")
        completed = await client.patch(
            f"/weekly-summary/daily-goals/today/{fake_weekly_summary_service.goal_id}",
            json={"completed": True},
        )
        updated = await client.get("/weekly-summary/daily-goals/today")

    assert initial.status_code == 200
    assert initial.json()["completion_rate"] == 0.0
    assert completed.status_code == 200
    assert completed.json()["completed"] is True
    assert updated.json()["completion_rate"] == 100.0
    assert updated.json()["all_completed"] is True


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
