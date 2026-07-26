from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.dependencies.auth import get_current_coach, get_current_user
from app.dependencies.workout_plan import get_workout_plan_service
from app.main import app
from app.models.coach_client import CoachClient, CoachClientStatus
from app.models.nutrition_plan import NutritionPlan
from app.models.user import User, UserRole
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_plan_repository import WorkoutPlanCompletionRepository
from app.schemas.workout_plan import AssignedWorkoutItemRead, AssignedWorkoutPlanRead
from app.services.workout_plan_service import (
    WorkoutItemNotFoundError,
    WorkoutPlanClientNotManagedError,
    WorkoutPlanNotFoundError,
    WorkoutPlanService,
)


class FakeWorkoutPlanService:
    def __init__(self, *, coach: User, client: User) -> None:
        self.coach = coach
        self.client = client
        self.plan_id = uuid4()
        self.item_id = uuid4()
        self.completed = False
        self.completed_at = None

    def _progress(self) -> AssignedWorkoutPlanRead:
        item = AssignedWorkoutItemRead(
            id=self.item_id,
            position=0,
            instruction="Do 30 pushups",
            completed=self.completed,
            completed_at=self.completed_at,
        )
        return AssignedWorkoutPlanRead(
            nutrition_plan_id=self.plan_id,
            coach_id=self.coach.id,
            client_id=self.client.id,
            valid_from=date(2026, 7, 26),
            valid_until=date(2026, 8, 1),
            validity_days=7,
            items=[item],
            completed_count=1 if self.completed else 0,
            total_count=1,
            completion_rate=100.0 if self.completed else 0.0,
            all_completed=self.completed,
        )

    def get_assigned_plan(self, *, current_user: User) -> AssignedWorkoutPlanRead:
        _ = current_user
        return self._progress()

    def update_completion(
        self,
        *,
        current_user: User,
        workout_item_id,
        completed: bool,
    ) -> AssignedWorkoutItemRead:
        _ = current_user
        if workout_item_id != self.item_id:
            raise WorkoutItemNotFoundError("Assigned workout item not found")
        self.completed = completed
        self.completed_at = datetime.now(tz=timezone.utc) if completed else None
        return self._progress().items[0]

    def get_assigned_plan_for_client(
        self,
        *,
        current_coach: User,
        client_id,
    ) -> AssignedWorkoutPlanRead:
        _ = current_coach
        if client_id != self.client.id:
            raise WorkoutPlanClientNotManagedError("Client is not assigned to this coach")
        return self._progress()


def _build_user(*, role: UserRole, email: str, full_name: str) -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        email=email,
        hashed_password="hashed-password",
        full_name=full_name,
        role=role,
        is_email_verified=True,
        is_active=True,
        use_reference_image=False,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def coach_user() -> User:
    return _build_user(
        role=UserRole.COACH,
        email="assigned.workout.coach@example.com",
        full_name="Assigned Workout Coach",
    )


@pytest.fixture
def client_user() -> User:
    return _build_user(
        role=UserRole.SELF,
        email="assigned.workout.client@example.com",
        full_name="Assigned Workout Client",
    )


@pytest.fixture
def fake_workout_plan_service(coach_user: User, client_user: User) -> FakeWorkoutPlanService:
    return FakeWorkoutPlanService(coach=coach_user, client=client_user)


@pytest.fixture
def override_workout_plan_service(fake_workout_plan_service: FakeWorkoutPlanService):
    app.dependency_overrides[get_workout_plan_service] = lambda: fake_workout_plan_service
    yield
    app.dependency_overrides.pop(get_workout_plan_service, None)


@pytest.fixture
def override_current_self(client_user: User):
    app.dependency_overrides[get_current_user] = lambda: client_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def override_current_coach(coach_user: User):
    app.dependency_overrides[get_current_coach] = lambda: coach_user
    yield
    app.dependency_overrides.pop(get_current_coach, None)


@pytest.mark.asyncio
async def test_self_gets_current_assigned_workout_plan(
    override_workout_plan_service,
    override_current_self,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/workout-plans/assigned")

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["instruction"] == "Do 30 pushups"
    assert data["items"][0]["completed"] is False
    assert data["validity_days"] == 7
    assert data["completion_rate"] == 0.0


@pytest.mark.asyncio
async def test_self_marks_and_unmarks_assigned_workout(
    override_workout_plan_service,
    override_current_self,
    fake_workout_plan_service: FakeWorkoutPlanService,
) -> None:
    item_id = fake_workout_plan_service.item_id
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        completed_response = await client.patch(
            f"/workout-plans/assigned/{item_id}",
            json={"completed": True},
        )
        progress_response = await client.get("/workout-plans/assigned")
        uncompleted_response = await client.patch(
            f"/workout-plans/assigned/{item_id}",
            json={"completed": False},
        )

    assert completed_response.status_code == 200
    assert completed_response.json()["completed"] is True
    assert completed_response.json()["completed_at"] is not None
    assert progress_response.json()["completed_count"] == 1
    assert progress_response.json()["all_completed"] is True
    assert uncompleted_response.status_code == 200
    assert uncompleted_response.json()["completed"] is False
    assert uncompleted_response.json()["completed_at"] is None


@pytest.mark.asyncio
async def test_coach_views_managed_client_workout_progress(
    override_workout_plan_service,
    override_current_coach,
    client_user: User,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/coach/clients/{client_user.id}/workout-plans/assigned"
        )

    assert response.status_code == 200
    assert response.json()["client_id"] == str(client_user.id)


def test_legacy_workout_crud_routes_are_removed() -> None:
    app.openapi_schema = None
    paths = app.openapi()["paths"]

    assert "/workout-plans" not in paths
    assert "/workout-plans/{plan_id}" not in paths
    assert "/workout-plans/{plan_id}/assign" not in paths
    assert "/workout-plans/assigned" in paths
    assert "/workout-plans/assigned/{workout_item_id}" in paths


def _create_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def _persist_user(session: Session, *, role: UserRole, email: str) -> User:
    user = User(
        email=email,
        hashed_password="hashed-password",
        full_name=email.split("@")[0],
        role=role,
        is_email_verified=True,
        is_active=True,
        use_reference_image=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _build_real_service(session: Session) -> WorkoutPlanService:
    return WorkoutPlanService(
        completion_repository=WorkoutPlanCompletionRepository(session),
        nutrition_plan_repository=NutritionPlanRepository(session),
        user_repository=UserRepository(session),
        coach_client_repository=CoachClientRepository(session),
    )


def test_completion_persists_for_active_nutrition_plan() -> None:
    session = _create_session()
    try:
        coach = _persist_user(
            session,
            role=UserRole.COACH,
            email="progress.coach@example.com",
        )
        client = _persist_user(
            session,
            role=UserRole.SELF,
            email="progress.client@example.com",
        )
        session.add(
            CoachClient(
                coach_id=coach.id,
                client_id=client.id,
                status=CoachClientStatus.ACCEPTED,
                assign_initial_plan=False,
            )
        )
        plan = NutritionPlan(
            coach_id=coach.id,
            client_id=client.id,
            date=date(2026, 7, 26),
            workout_plan=["Do 30 pushups", "Walk for 20 minutes"],
            daily_goals=[],
        )
        session.add(plan)
        session.commit()
        session.refresh(plan)

        service = _build_real_service(session)
        initial = service.get_assigned_plan(
            current_user=client,
            target_date=date(2026, 7, 26),
        )
        assert initial.total_count == 2
        assert initial.items[0].id != initial.items[1].id
        assert initial.completed_count == 0

        marked = service.update_completion(
            current_user=client,
            workout_item_id=initial.items[0].id,
            completed=True,
            target_date=date(2026, 7, 26),
        )
        updated = service.get_assigned_plan(
            current_user=client,
            target_date=date(2026, 8, 1),
        )

        assert marked.completed is True
        assert updated.items[0].id == initial.items[0].id
        assert updated.items[0].completed is True
        assert updated.completed_count == 1
        assert updated.completion_rate == 50.0
        assert updated.all_completed is False

        unmarked = service.update_completion(
            current_user=client,
            workout_item_id=initial.items[0].id,
            completed=False,
            target_date=date(2026, 7, 26),
        )
        assert unmarked.completed is False
        assert unmarked.completed_at is None
    finally:
        session.close()


def test_cannot_mark_unknown_or_expired_workout_item() -> None:
    session = _create_session()
    try:
        coach = _persist_user(
            session,
            role=UserRole.COACH,
            email="expired.workout.coach@example.com",
        )
        client = _persist_user(
            session,
            role=UserRole.SELF,
            email="expired.workout.client@example.com",
        )
        session.add(
            CoachClient(
                coach_id=coach.id,
                client_id=client.id,
                status=CoachClientStatus.ACCEPTED,
                assign_initial_plan=False,
            )
        )
        session.add(
            NutritionPlan(
                coach_id=coach.id,
                client_id=client.id,
                date=date(2026, 7, 1),
                workout_plan=["Do 20 squats"],
                daily_goals=[],
            )
        )
        session.commit()
        service = _build_real_service(session)

        with pytest.raises(WorkoutItemNotFoundError):
            service.update_completion(
                current_user=client,
                workout_item_id=uuid4(),
                completed=True,
                target_date=date(2026, 7, 1),
            )

        with pytest.raises(WorkoutPlanNotFoundError, match="No active workout plan assigned"):
            service.get_assigned_plan(
                current_user=client,
                target_date=date(2026, 7, 8),
            )
    finally:
        session.close()


def test_pending_coach_cannot_view_client_progress() -> None:
    session = _create_session()
    try:
        coach = _persist_user(
            session,
            role=UserRole.COACH,
            email="pending.progress.coach@example.com",
        )
        client = _persist_user(
            session,
            role=UserRole.SELF,
            email="pending.progress.client@example.com",
        )
        session.add(
            CoachClient(
                coach_id=coach.id,
                client_id=client.id,
                status=CoachClientStatus.PENDING,
                assign_initial_plan=False,
            )
        )
        session.commit()
        service = _build_real_service(session)

        with pytest.raises(WorkoutPlanClientNotManagedError):
            service.get_assigned_plan_for_client(
                current_coach=coach,
                client_id=client.id,
                target_date=date(2026, 7, 26),
            )
    finally:
        session.close()
