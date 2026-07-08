from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_user
from app.dependencies.routine import get_routine_service
from app.main import app
from app.models.routine import Routine
from app.models.user import User, UserRole
from app.schemas.routine import RoutineCreate, RoutinePatch, RoutinePut
from app.services.routine_service import (
    EmptyRoutineUpdateError,
    RoutineAlreadyExistsError,
    RoutineNotFoundError,
)


class FakeRoutineService:
    def __init__(self, user: User) -> None:
        self.user = user
        now = datetime.now(tz=timezone.utc)
        initial_routine = Routine(
            id=uuid4(),
            user_id=user.id,
            date=date(2026, 6, 30),
            workout="Morning run",
            meals="Oats and salad",
            water_intake=2.0,
            sleep=7.5,
            notes="Felt energetic",
            completion_status=True,
            created_at=now,
            updated_at=now,
        )
        self.routines = {initial_routine.id: initial_routine}

    def create_routine(self, *, current_user: User, payload: RoutineCreate) -> Routine:
        for routine in self.routines.values():
            if routine.user_id == current_user.id and routine.date == payload.date:
                raise RoutineAlreadyExistsError("Only one routine is allowed per user per day")

        now = datetime.now(tz=timezone.utc)
        routine = Routine(
            id=uuid4(),
            user_id=current_user.id,
            date=payload.date,
            workout=payload.workout,
            meals=payload.meals,
            water_intake=payload.water_intake,
            sleep=payload.sleep,
            notes=payload.notes,
            completion_status=payload.completion_status,
            created_at=now,
            updated_at=now,
        )
        self.routines[routine.id] = routine
        return routine

    def list_routines(self, *, current_user: User) -> list[Routine]:
        return [routine for routine in self.routines.values() if routine.user_id == current_user.id]

    def get_routine(self, *, current_user: User, routine_id) -> Routine:
        routine = self.routines.get(routine_id)
        if routine is None or routine.user_id != current_user.id:
            raise RoutineNotFoundError("Routine not found")
        return routine

    def replace_routine(self, *, current_user: User, routine_id, payload: RoutinePut) -> Routine:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)
        for existing in self.routines.values():
            if (
                existing.id != routine.id
                and existing.user_id == current_user.id
                and existing.date == payload.date
            ):
                raise RoutineAlreadyExistsError("Only one routine is allowed per user per day")

        routine.date = payload.date
        routine.workout = payload.workout
        routine.meals = payload.meals
        routine.water_intake = payload.water_intake
        routine.sleep = payload.sleep
        routine.notes = payload.notes
        routine.completion_status = payload.completion_status
        routine.updated_at = datetime.now(tz=timezone.utc)
        return routine

    def patch_routine(self, *, current_user: User, routine_id, payload: RoutinePatch) -> Routine:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise EmptyRoutineUpdateError("No routine fields were provided")

        if "date" in updates:
            for existing in self.routines.values():
                if (
                    existing.id != routine.id
                    and existing.user_id == current_user.id
                    and existing.date == updates["date"]
                ):
                    raise RoutineAlreadyExistsError("Only one routine is allowed per user per day")

        for key, value in updates.items():
            setattr(routine, key, value)
        routine.updated_at = datetime.now(tz=timezone.utc)
        return routine

    def delete_routine(self, *, current_user: User, routine_id) -> None:
        routine = self.routines.get(routine_id)
        if routine is None or routine.user_id != current_user.id:
            raise RoutineNotFoundError("Routine not found")
        del self.routines[routine_id]


@pytest.fixture
def current_user() -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        username="routine_user",
        email="routine.user@example.com",
        hashed_password="hashed-password",
        full_name="Routine User",
        age=None,
        date_of_birth=date(1999, 2, 2),
        gender="male",
        occupation="Developer",
        fitness_goal="Stay fit",
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
def fake_routine_service(current_user: User) -> FakeRoutineService:
    return FakeRoutineService(current_user)


@pytest.fixture
def override_routine_service(fake_routine_service: FakeRoutineService):
    app.dependency_overrides[get_routine_service] = lambda: fake_routine_service
    yield
    app.dependency_overrides.pop(get_routine_service, None)


@pytest.fixture
def override_current_user(current_user: User):
    app.dependency_overrides[get_current_user] = lambda: current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_list_routines(override_routine_service, override_current_user) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/routines")

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_create_routine_success(override_routine_service, override_current_user) -> None:
    payload = {
        "date": "2026-07-01",
        "workout": "Leg day",
        "meals": "Chicken and rice",
        "water_intake": 2.5,
        "sleep": 8.0,
        "notes": "Strong session",
        "completion_status": False,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/routines", json=payload)

    assert response.status_code == 201
    assert response.json()["date"] == "2026-07-01"


@pytest.mark.asyncio
async def test_create_routine_duplicate_date(override_routine_service, override_current_user) -> None:
    payload = {
        "date": "2026-06-30",
        "workout": "Duplicate",
        "meals": "Duplicate",
        "water_intake": 1.5,
        "sleep": 7.0,
        "notes": "Duplicate",
        "completion_status": True,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/routines", json=payload)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_routine_not_found(override_routine_service, override_current_user) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"/routines/{uuid4()}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_put_routine(override_routine_service, override_current_user, fake_routine_service: FakeRoutineService) -> None:
    routine_id = next(iter(fake_routine_service.routines.keys()))
    payload = {
        "date": "2026-07-02",
        "workout": "Upper body",
        "meals": "High protein",
        "water_intake": 3.0,
        "sleep": 7.8,
        "notes": "Good progress",
        "completion_status": True,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.put(f"/routines/{routine_id}", json=payload)

    assert response.status_code == 200
    assert response.json()["workout"] == "Upper body"


@pytest.mark.asyncio
async def test_patch_routine_empty_payload(
    override_routine_service,
    override_current_user,
    fake_routine_service: FakeRoutineService,
) -> None:
    routine_id = next(iter(fake_routine_service.routines.keys()))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.patch(f"/routines/{routine_id}", json={})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_routine(override_routine_service, override_current_user, fake_routine_service: FakeRoutineService) -> None:
    routine_id = next(iter(fake_routine_service.routines.keys()))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.delete(f"/routines/{routine_id}")

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_routines_require_authentication(override_routine_service) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/routines")

    assert response.status_code == 401