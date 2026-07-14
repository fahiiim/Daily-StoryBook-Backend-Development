from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_user
from app.dependencies.routine import get_routine_service
from app.main import app
from app.models.routine import Routine
from app.models.routine_macro_log import MacroType, RoutineMacroLog
from app.models.user import User, UserRole
from app.schemas.routine import RoutineCreate, RoutineMacroLogCreate, RoutinePatch, RoutinePut
from app.services.routine_service import (
    EmptyRoutineUpdateError,
    RoutineRecentFood,
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
            meals_kcal=450.0,
            goal_kcal=2200.0,
            goal_protein=150.0,
            goal_carbs=250.0,
            goal_fats=70.0,
            goal_fiber=30.0,
            intake_protein=80.0,
            intake_carbs=100.0,
            intake_fats=30.0,
            intake_fiber=10.0,
            water_intake=2.0,
            sleep=7.5,
            notes="Felt energetic",
            completion_status=True,
            created_at=now,
            updated_at=now,
        )
        self.routines = {initial_routine.id: initial_routine}
        self.macro_logs: dict = {}

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
            meals_kcal=payload.meals_kcal,
            goal_kcal=payload.goal_kcal,
            goal_protein=payload.goal_protein,
            goal_carbs=payload.goal_carbs,
            goal_fats=payload.goal_fats,
            goal_fiber=payload.goal_fiber,
            intake_protein=payload.intake_protein,
            intake_carbs=payload.intake_carbs,
            intake_fats=payload.intake_fats,
            intake_fiber=payload.intake_fiber,
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

    def get_or_create_routine_for_date(self, *, current_user: User, target_date: date) -> Routine:
        for routine in self.routines.values():
            if routine.user_id == current_user.id and routine.date == target_date:
                return routine

        now = datetime.now(tz=timezone.utc)
        routine = Routine(
            id=uuid4(),
            user_id=current_user.id,
            date=target_date,
            completion_status=False,
            created_at=now,
            updated_at=now,
        )
        self.routines[routine.id] = routine
        return routine

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
        routine.meals_kcal = payload.meals_kcal
        routine.goal_kcal = payload.goal_kcal
        routine.goal_protein = payload.goal_protein
        routine.goal_carbs = payload.goal_carbs
        routine.goal_fats = payload.goal_fats
        routine.goal_fiber = payload.goal_fiber
        routine.intake_protein = payload.intake_protein
        routine.intake_carbs = payload.intake_carbs
        routine.intake_fats = payload.intake_fats
        routine.intake_fiber = payload.intake_fiber
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

    def add_macro_log(
        self,
        *,
        current_user: User,
        routine_id,
        payload: RoutineMacroLogCreate,
    ) -> tuple[Routine, RoutineMacroLog]:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)
        log = RoutineMacroLog(
            id=uuid4(),
            routine_id=routine.id,
            user_id=current_user.id,
            macro_type=payload.macro_type,
            food_name=payload.food_name,
            amount=payload.amount,
            amount_unit=payload.amount_unit,
            macro_grams=payload.macro_grams,
            kcal=payload.kcal,
            logged_at=payload.logged_at or datetime.now(tz=timezone.utc),
        )
        self.macro_logs[log.id] = log

        if payload.macro_type == MacroType.PROTEIN:
            routine.intake_protein = round((routine.intake_protein or 0.0) + payload.macro_grams, 2)
        elif payload.macro_type == MacroType.CARBS:
            routine.intake_carbs = round((routine.intake_carbs or 0.0) + payload.macro_grams, 2)
        elif payload.macro_type == MacroType.FATS:
            routine.intake_fats = round((routine.intake_fats or 0.0) + payload.macro_grams, 2)
        elif payload.macro_type == MacroType.FIBER:
            routine.intake_fiber = round((routine.intake_fiber or 0.0) + payload.macro_grams, 2)

        routine.meals_kcal = round((routine.meals_kcal or 0.0) + payload.kcal, 2)
        routine.updated_at = datetime.now(tz=timezone.utc)
        return routine, log

    def list_macro_logs(self, *, current_user: User, routine_id) -> list[RoutineMacroLog]:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)
        return sorted(
            [
                log
                for log in self.macro_logs.values()
                if log.user_id == current_user.id and log.routine_id == routine.id
            ],
            key=lambda log: log.logged_at,
            reverse=True,
        )

    def list_recent_macro_foods(
        self,
        *,
        current_user: User,
        macro_type: MacroType,
        limit: int,
    ) -> list[RoutineRecentFood]:
        recent_logs = sorted(
            [
                log
                for log in self.macro_logs.values()
                if log.user_id == current_user.id and log.macro_type == macro_type
            ],
            key=lambda log: log.logged_at,
            reverse=True,
        )
        seen_foods: set[str] = set()
        recent_foods: list[RoutineRecentFood] = []
        for log in recent_logs:
            key = log.food_name.lower()
            if key in seen_foods:
                continue
            seen_foods.add(key)
            recent_foods.append(
                RoutineRecentFood(
                    macro_type=log.macro_type,
                    food_name=log.food_name,
                    amount=log.amount,
                    amount_unit=log.amount_unit,
                    macro_grams=log.macro_grams,
                    kcal=log.kcal,
                    last_logged_at=log.logged_at,
                )
            )
            if len(recent_foods) >= limit:
                break

        return recent_foods


@pytest.fixture
def current_user() -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
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
async def test_get_today_routine_supports_macro_dashboard_flow(
    override_routine_service,
    override_current_user,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/routines/today", params={"routine_date": "2026-07-03"})

    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2026-07-03"
    assert data["completion_status"] is False


@pytest.mark.asyncio
async def test_add_macro_log_updates_daily_log_and_recent_foods(
    override_routine_service,
    override_current_user,
    fake_routine_service: FakeRoutineService,
) -> None:
    routine_id = next(iter(fake_routine_service.routines.keys()))
    payload = {
        "macro_type": "PROTEIN",
        "food_name": "Chicken Breast",
        "amount": 100,
        "amount_unit": "grams",
        "macro_grams": 31,
        "kcal": 165,
        "logged_at": "2026-07-01T08:00:00Z",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        add_response = await client.post(f"/routines/{routine_id}/macro-logs", json=payload)
        logs_response = await client.get(f"/routines/{routine_id}/macro-logs")
        recent_response = await client.get(
            "/routines/macro-recent",
            params={"macro_type": "PROTEIN", "limit": 4},
        )

    assert add_response.status_code == 201
    add_payload = add_response.json()
    assert add_payload["log"]["food_name"] == "Chicken Breast"
    assert add_payload["routine"]["intake_protein"] == 111.0
    assert add_payload["routine"]["meals_kcal"] == 615.0

    assert logs_response.status_code == 200
    assert logs_response.json()[0]["food_name"] == "Chicken Breast"

    assert recent_response.status_code == 200
    assert recent_response.json()[0]["food_name"] == "Chicken Breast"


@pytest.mark.asyncio
async def test_add_today_macro_log_uses_daily_routine_without_uuid(
    override_routine_service,
    override_current_user,
) -> None:
    payload = {
        "macro_type": "PROTEIN",
        "food_name": "Beef Steak",
        "amount": 250,
        "amount_unit": "grams",
        "macro_grams": 20,
        "kcal": 720,
        "logged_at": "2026-07-13T05:00:31.953Z",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/routines/today/macro-logs",
            params={"routine_date": "2026-07-13"},
            json=payload,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["routine"]["date"] == "2026-07-13"
    assert data["routine"]["intake_protein"] == 20.0
    assert data["routine"]["meals_kcal"] == 720.0
    assert data["log"]["food_name"] == "Beef Steak"


@pytest.mark.asyncio
async def test_create_routine_success(override_routine_service, override_current_user) -> None:
    payload = {
        "date": "2026-07-01",
        "workout": "Leg day",
        "meals": "Chicken and rice",
        "meals_kcal": 1600.0,
        "goal_kcal": 2200.0,
        "goal_protein": 150.0,
        "goal_carbs": 250.0,
        "goal_fats": 70.0,
        "goal_fiber": 30.0,
        "intake_protein": 100.0,
        "intake_carbs": 120.0,
        "intake_fats": 40.0,
        "intake_fiber": 20.0,
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
    data = response.json()
    assert data["consumed_kcal"] == 1600.0
    assert data["remaining_kcal"] == 600.0
    assert data["remaining_protein"] == 50.0
    assert data["remaining_carbs"] == 130.0
    assert data["remaining_fats"] == 30.0
    assert data["remaining_fiber"] == 10.0
    assert data["meals"] == "Chicken and rice"
    assert data["notes"] == "Strong session"


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
        "meals_kcal": 2490.0,
        "goal_kcal": 2400.0,
        "goal_protein": 180.0,
        "goal_carbs": 260.0,
        "goal_fats": 80.0,
        "goal_fiber": 35.0,
        "intake_protein": 190.0,
        "intake_carbs": 260.0,
        "intake_fats": 90.0,
        "intake_fiber": 40.0,
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
    data = response.json()
    assert data["remaining_kcal"] == -90.0
    assert data["remaining_protein"] == -10.0
    assert data["remaining_carbs"] == 0.0
    assert data["remaining_fats"] == -10.0
    assert data["remaining_fiber"] == -5.0


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
async def test_patch_routine_macro_intake_and_notes(
    override_routine_service,
    override_current_user,
    fake_routine_service: FakeRoutineService,
) -> None:
    routine_id = next(iter(fake_routine_service.routines.keys()))

    payload = {
        "intake_protein": 120.0,
        "intake_carbs": 140.0,
        "intake_fats": 45.0,
        "intake_fiber": 18.0,
        "meals_kcal": 1741.0,
        "meals": "Oats, chicken bowl, yogurt",
        "notes": "Tracked all meals",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.patch(f"/routines/{routine_id}", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["meals"] == "Oats, chicken bowl, yogurt"
    assert data["notes"] == "Tracked all meals"
    assert data["consumed_kcal"] == 1741.0
    assert data["remaining_kcal"] == 459.0


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