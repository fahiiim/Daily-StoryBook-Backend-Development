from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_coach, get_current_user
from app.dependencies.workout_plan import get_workout_plan_service
from app.main import app
from app.models.user import User, UserRole
from app.models.workout_plan import WorkoutPlan, WorkoutPlanAssignment
from app.schemas.workout_plan import WorkoutPlanCreate, WorkoutPlanPatch, WorkoutPlanPut
from app.services.workout_plan_service import (
    EmptyWorkoutPlanUpdateError,
    WorkoutPlanAssignmentExistsError,
    WorkoutPlanClientNotFoundError,
    WorkoutPlanClientNotManagedError,
    WorkoutPlanNotFoundError,
)


class FakeWorkoutPlanService:
    def __init__(self, *, coach_user: User, clients: list[User]) -> None:
        self.coach_user = coach_user
        self.clients = {client.id: client for client in clients}
        self.managed_client_ids = {client.id for client in clients}

        now = datetime.now(tz=timezone.utc)
        initial_plan = WorkoutPlan(
            id=uuid4(),
            coach_id=coach_user.id,
            title="Starter Plan",
            description="Basic weekly routine",
            exercises="Pushups, Squats",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.plans = {initial_plan.id: initial_plan}

        self.assignments: set[tuple] = {(initial_plan.id, clients[0].id)}

    def create_plan(self, *, current_coach: User, payload: WorkoutPlanCreate) -> WorkoutPlan:
        now = datetime.now(tz=timezone.utc)
        plan = WorkoutPlan(
            id=uuid4(),
            coach_id=current_coach.id,
            title=payload.title,
            description=payload.description,
            exercises=payload.exercises,
            is_active=payload.is_active,
            created_at=now,
            updated_at=now,
        )
        self.plans[plan.id] = plan
        return plan

    def replace_plan(self, *, current_coach: User, plan_id, payload: WorkoutPlanPut) -> WorkoutPlan:
        plan = self._get_owned_plan(current_coach=current_coach, plan_id=plan_id)
        plan.title = payload.title
        plan.description = payload.description
        plan.exercises = payload.exercises
        plan.is_active = payload.is_active
        plan.updated_at = datetime.now(tz=timezone.utc)
        return plan

    def patch_plan(self, *, current_coach: User, plan_id, payload: WorkoutPlanPatch) -> WorkoutPlan:
        plan = self._get_owned_plan(current_coach=current_coach, plan_id=plan_id)
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise EmptyWorkoutPlanUpdateError("No workout plan fields were provided")

        for field_name, value in updates.items():
            setattr(plan, field_name, value)
        plan.updated_at = datetime.now(tz=timezone.utc)
        return plan

    def delete_plan(self, *, current_coach: User, plan_id) -> None:
        self._get_owned_plan(current_coach=current_coach, plan_id=plan_id)
        del self.plans[plan_id]
        self.assignments = {item for item in self.assignments if item[0] != plan_id}

    def assign_plan_to_client(self, *, current_coach: User, plan_id, client_id) -> WorkoutPlanAssignment:
        plan = self._get_owned_plan(current_coach=current_coach, plan_id=plan_id)

        if client_id not in self.clients:
            raise WorkoutPlanClientNotFoundError("Client not found")
        if client_id not in self.managed_client_ids:
            raise WorkoutPlanClientNotManagedError("Client is not assigned to this coach")
        if (plan.id, client_id) in self.assignments:
            raise WorkoutPlanAssignmentExistsError("Workout plan already assigned to this client")

        assignment = WorkoutPlanAssignment(
            id=uuid4(),
            plan_id=plan.id,
            client_id=client_id,
            assigned_by_coach_id=current_coach.id,
            created_at=datetime.now(tz=timezone.utc),
        )
        self.assignments.add((plan.id, client_id))
        return assignment

    def list_viewable_plans(self, *, current_user: User) -> list[WorkoutPlan]:
        if current_user.role == UserRole.COACH:
            return [plan for plan in self.plans.values() if plan.coach_id == current_user.id]

        plan_ids = [plan_id for plan_id, client_id in self.assignments if client_id == current_user.id]
        return [self.plans[plan_id] for plan_id in plan_ids if plan_id in self.plans]

    def get_viewable_plan(self, *, current_user: User, plan_id) -> WorkoutPlan:
        plan = self.plans.get(plan_id)
        if plan is None:
            raise WorkoutPlanNotFoundError("Workout plan not found")

        if current_user.role == UserRole.COACH and plan.coach_id == current_user.id:
            return plan

        if current_user.role != UserRole.COACH and (plan_id, current_user.id) in self.assignments:
            return plan

        raise WorkoutPlanNotFoundError("Workout plan not found")

    def _get_owned_plan(self, *, current_coach: User, plan_id) -> WorkoutPlan:
        plan = self.plans.get(plan_id)
        if plan is None or plan.coach_id != current_coach.id:
            raise WorkoutPlanNotFoundError("Workout plan not found")
        return plan


def _build_user(*, role: UserRole, email: str, full_name: str) -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        email=email,
        hashed_password="hashed-password",
        full_name=full_name,
        age=30,
        gender="male",
        occupation="Coach",
        fitness_goal="Build stamina",
        profile_image=None,
        reference_image=None,
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def coach_user() -> User:
    return _build_user(role=UserRole.COACH, email="coach.plan@example.com", full_name="Coach Plan")


@pytest.fixture
def client_user() -> User:
    return _build_user(role=UserRole.SELF, email="client.plan@example.com", full_name="Client Plan")


@pytest.fixture
def clients(client_user: User) -> list[User]:
    return [client_user]


@pytest.fixture
def fake_workout_plan_service(coach_user: User, clients: list[User]) -> FakeWorkoutPlanService:
    return FakeWorkoutPlanService(coach_user=coach_user, clients=clients)


@pytest.fixture
def override_workout_plan_service(fake_workout_plan_service: FakeWorkoutPlanService):
    app.dependency_overrides[get_workout_plan_service] = lambda: fake_workout_plan_service
    yield
    app.dependency_overrides.pop(get_workout_plan_service, None)


@pytest.fixture
def override_current_coach(coach_user: User):
    app.dependency_overrides[get_current_coach] = lambda: coach_user
    yield
    app.dependency_overrides.pop(get_current_coach, None)


@pytest.fixture
def override_current_user_as_client(client_user: User):
    app.dependency_overrides[get_current_user] = lambda: client_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_coach_create_plan(override_workout_plan_service, override_current_coach) -> None:
    payload = {
        "title": "Strength Plan",
        "description": "4-week strength block",
        "exercises": "Squat, Bench, Deadlift",
        "is_active": True,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/workout-plans", json=payload)

    assert response.status_code == 201
    assert response.json()["title"] == "Strength Plan"


@pytest.mark.asyncio
async def test_coach_patch_plan(
    override_workout_plan_service,
    override_current_coach,
    fake_workout_plan_service: FakeWorkoutPlanService,
) -> None:
    plan_id = next(iter(fake_workout_plan_service.plans.keys()))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.patch(
            f"/workout-plans/{plan_id}",
            json={"title": "Updated Starter Plan"},
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Starter Plan"


@pytest.mark.asyncio
async def test_coach_delete_plan(
    override_workout_plan_service,
    override_current_coach,
    fake_workout_plan_service: FakeWorkoutPlanService,
) -> None:
    plan_id = next(iter(fake_workout_plan_service.plans.keys()))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.delete(f"/workout-plans/{plan_id}")

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_assign_plan_prevents_duplicates(
    override_workout_plan_service,
    override_current_coach,
    fake_workout_plan_service: FakeWorkoutPlanService,
    client_user: User,
) -> None:
    plan_id = next(iter(fake_workout_plan_service.plans.keys()))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            f"/workout-plans/{plan_id}/assign",
            json={"client_id": str(client_user.id)},
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_client_can_only_view(
    override_workout_plan_service,
    override_current_user_as_client,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/workout-plans")

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_client_cannot_create_plan(
    override_workout_plan_service,
    override_current_user_as_client,
) -> None:
    payload = {
        "title": "Unauthorized Plan",
        "description": "Not allowed",
        "exercises": "Run",
        "is_active": True,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/workout-plans", json=payload)

    assert response.status_code == 403