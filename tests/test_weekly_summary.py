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
    WeeklyGoalDayRead,
    WeeklyGoalsRead,
    WeeklyMealDayRead,
    WeeklyMealRemainingRead,
    WeeklyMealsRead,
    WeeklyMealTargetsRead,
    WeeklyMealTotalsRead,
    WeeklyProgressAnalyticsRead,
    WeeklyProgressAverages,
    WeeklyProgressCoverage,
    WeeklyWorkoutDayRead,
    WeeklyWorkoutsRead,
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

    def _base(self) -> dict[str, object]:
        return {
            "user_id": self.current_user.id,
            "week_start": date(2026, 7, 20),
            "week_end": date(2026, 7, 26),
            "as_of_date": date(2026, 7, 26),
            "as_of": datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc),
            "is_partial_week": False,
        }

    def get_current_week_workouts(self, *, current_user: User):
        _ = current_user
        return WeeklyWorkoutsRead(
            **self._base(),
            days=[
                WeeklyWorkoutDayRead(
                    date=date(2026, 7, 20) + timedelta(days=index),
                    day=(date(2026, 7, 20) + timedelta(days=index)).strftime("%a").upper(),
                    is_future=False,
                    applicable=False,
                    plan=None,
                    workout_score=None,
                    completed_count=0,
                    assigned_count=0,
                    all_completed=None,
                )
                for index in range(7)
            ],
        )

    def get_current_week_meals(self, *, current_user: User):
        _ = current_user
        return WeeklyMealsRead(
            **self._base(),
            days=[
                WeeklyMealDayRead(
                    date=date(2026, 7, 20) + timedelta(days=index),
                    day=(date(2026, 7, 20) + timedelta(days=index)).strftime("%a").upper(),
                    is_future=False,
                    applicable=False,
                    plan=None,
                    routine_id=None,
                    meal_score=None,
                    components_scored=0,
                    components_met=0,
                    completed=None,
                    targets=WeeklyMealTargetsRead(
                        kcal=None,
                        protein=None,
                        carbs=None,
                        fat=None,
                        fiber=None,
                        water=None,
                    ),
                    consumed=WeeklyMealTotalsRead(
                        kcal=0,
                        protein=0,
                        carbs=0,
                        fat=0,
                        fiber=0,
                        water=0,
                    ),
                    remaining=WeeklyMealRemainingRead(
                        kcal=None,
                        protein=None,
                        carbs=None,
                        fat=None,
                        fiber=None,
                        water=None,
                    ),
                )
                for index in range(7)
            ],
        )

    def get_current_week_goals(self, *, current_user: User):
        _ = current_user
        return WeeklyGoalsRead(
            **self._base(),
            days=[
                WeeklyGoalDayRead(
                    date=date(2026, 7, 20) + timedelta(days=index),
                    day=(date(2026, 7, 20) + timedelta(days=index)).strftime("%a").upper(),
                    is_future=False,
                    applicable=False,
                    plan=None,
                    daily_goal_score=None,
                    completed_count=0,
                    assigned_count=0,
                    all_completed=None,
                )
                for index in range(7)
            ],
        )

    def get_client_current_week_analytics(self, *, current_coach: User, client_id):
        _ = current_coach
        _ = client_id
        return self.get_current_week_analytics(current_user=self.current_user)

    def get_client_current_week_workouts(self, *, current_coach: User, client_id):
        _ = current_coach
        _ = client_id
        return self.get_current_week_workouts(current_user=self.current_user)

    def get_client_current_week_meals(self, *, current_coach: User, client_id):
        _ = current_coach
        _ = client_id
        return self.get_current_week_meals(current_user=self.current_user)

    def get_client_current_week_goals(self, *, current_coach: User, client_id):
        _ = current_coach
        _ = client_id
        return self.get_current_week_goals(current_user=self.current_user)


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
def coach_user() -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        email="weekly.coach@example.com",
        hashed_password="hashed-password",
        full_name="Weekly Coach",
        role=UserRole.COACH,
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
def override_current_coach(coach_user: User):
    app.dependency_overrides[get_current_user] = lambda: coach_user
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
    assert payload["weekly_progress_percentage"] == 75.0


@pytest.mark.asyncio
async def test_self_gets_weekly_workouts_meals_and_goals(
    override_current_user,
    override_weekly_summary_service,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        workouts = await client.get("/weekly-summary/workouts")
        meals = await client.get("/weekly-summary/meals")
        goals = await client.get("/weekly-summary/goals")

    assert workouts.status_code == 200
    assert meals.status_code == 200
    assert goals.status_code == 200
    assert len(workouts.json()["days"]) == 7
    assert len(meals.json()["days"]) == 7
    assert len(goals.json()["days"]) == 7


@pytest.mark.asyncio
async def test_coach_gets_managed_client_weekly_data(
    override_current_coach,
    override_weekly_summary_service,
    current_user: User,
) -> None:
    prefix = f"/coach/clients/{current_user.id}/weekly-summary"
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        responses = [
            await client.get(prefix),
            await client.get(f"{prefix}/workouts"),
            await client.get(f"{prefix}/meals"),
            await client.get(f"{prefix}/goals"),
        ]

    assert all(response.status_code == 200 for response in responses)


def test_weekly_summary_routes_are_read_only_and_self_routes_have_no_parameters() -> None:
    app.openapi_schema = None
    paths = app.openapi()["paths"]

    assert "/weekly-summary" in paths
    self_paths = [
        "/weekly-summary",
        "/weekly-summary/workouts",
        "/weekly-summary/meals",
        "/weekly-summary/goals",
    ]
    coach_paths = [
        "/coach/clients/{client_id}/weekly-summary",
        "/coach/clients/{client_id}/weekly-summary/workouts",
        "/coach/clients/{client_id}/weekly-summary/meals",
        "/coach/clients/{client_id}/weekly-summary/goals",
    ]
    assert all(sorted(paths[path]) == ["get"] for path in self_paths + coach_paths)
    assert all(paths[path]["get"].get("parameters", []) == [] for path in self_paths)
    analytics_schema = app.openapi()["components"]["schemas"]["WeeklyProgressAnalyticsRead"]
    assert "weekly_progress_percentage" in analytics_schema["properties"]
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
