from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_user
from app.dependencies.routine import get_routine_service
from app.main import app
from app.models.nutrition_plan import NutritionPlan
from app.models.routine import Routine
from app.models.routine_macro_log import MacroType, RoutineMacroLog
from app.models.user import User, UserRole
from app.schemas.routine import (
    RoutineCreate,
    RoutineMacroLogCreate,
    RoutineMacroLogUpdate,
    RoutinePatch,
    RoutinePut,
)
from app.services.routine_service import (
    EmptyRoutineUpdateError,
    RoutineMacroLogNotFoundError,
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

    def _nutrition_plan(self, *, client_id, plan_date) -> NutritionPlan:
        now = datetime.now(tz=timezone.utc)
        return NutritionPlan(
            id=uuid4(),
            coach_id=uuid4(),
            client_id=client_id,
            daily_calories=2200,
            protein=150,
            carbs=250,
            fat=70,
            fiber=30,
            water_goal=3.0,
            workout_plan=["Do 30 pushups", "Walk for 20 minutes"],
            daily_goals=["Drink 3 litres of water", "Sleep for 8 hours"],
            notes="Coach targets",
            date=plan_date,
            created_at=now,
            updated_at=now,
        )

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
            meals_kcal=None,
            goal_kcal=None,
            goal_protein=None,
            goal_carbs=None,
            goal_fats=None,
            goal_fiber=None,
            intake_protein=None,
            intake_carbs=None,
            intake_fats=None,
            intake_fiber=None,
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

    def get_routine_for_date(self, *, current_user: User, target_date: date) -> Routine | None:
        for routine in self.routines.values():
            if routine.user_id == current_user.id and routine.date == target_date:
                return routine
        return None

    def get_nutrition_plan_for_date(self, *, client_id, routine_date, coach_id=None):
        _ = coach_id
        return self._nutrition_plan(client_id=client_id, plan_date=routine_date)

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
            macro_type=MacroType.PROTEIN,
            meal_type=payload.meal_type,
            food_name=payload.food_name,
            amount=payload.amount,
            amount_unit=payload.amount_unit,
            macro_grams=payload.protein,
            kcal=payload.kcal,
            protein=payload.protein,
            carbs=payload.carbs,
            fat=payload.fat,
            fiber=payload.fiber,
            logged_at=payload.logged_at or datetime.now(tz=timezone.utc),
        )
        self.macro_logs[log.id] = log
        self._recalculate(routine)
        routine.updated_at = datetime.now(tz=timezone.utc)
        return routine, log

    def update_macro_log(
        self,
        *,
        current_user: User,
        routine_id,
        log_id,
        payload: RoutineMacroLogUpdate,
    ) -> tuple[Routine, RoutineMacroLog]:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)
        log = self.macro_logs.get(log_id)
        if log is None or log.routine_id != routine.id or log.user_id != current_user.id:
            raise RoutineMacroLogNotFoundError("Logged meal not found")
        for field_name, value in payload.model_dump(exclude_unset=True).items():
            setattr(log, field_name, value)
        self._recalculate(routine)
        return routine, log

    def delete_macro_log(self, *, current_user: User, routine_id, log_id) -> Routine:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)
        log = self.macro_logs.get(log_id)
        if log is None or log.routine_id != routine.id or log.user_id != current_user.id:
            raise RoutineMacroLogNotFoundError("Logged meal not found")
        del self.macro_logs[log_id]
        self._recalculate(routine)
        return routine

    def _recalculate(self, routine: Routine) -> None:
        logs = [log for log in self.macro_logs.values() if log.routine_id == routine.id]
        routine.meals_kcal = round(sum(log.kcal for log in logs), 2)
        routine.intake_protein = round(sum(log.protein for log in logs), 2)
        routine.intake_carbs = round(sum(log.carbs for log in logs), 2)
        routine.intake_fats = round(sum(log.fat for log in logs), 2)
        routine.intake_fiber = round(sum(log.fiber for log in logs), 2)

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
                    kcal=log.kcal,
                    protein=log.protein,
                    carbs=log.carbs,
                    fat=log.fat,
                    fiber=log.fiber,
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
    assert data["nutrition_plan"]["daily_calories"] == 2200
    assert data["nutrition_plan"]["water_goal"] == 3.0
    assert data["nutrition_plan"]["fiber"] == 30.0
    assert data["nutrition_plan"]["workout_plan"] == [
        "Do 30 pushups",
        "Walk for 20 minutes",
    ]
    assert data["nutrition_plan"]["daily_goals"] == [
        "Drink 3 litres of water",
        "Sleep for 8 hours",
    ]


@pytest.mark.asyncio
async def test_today_dashboard_exposes_nutrition_targets_and_water_goal(
    override_routine_service,
    override_current_user,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/routines/today/dashboard",
            params={"routine_date": "2026-06-30"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["nutrition_plan"]["daily_calories"] == 2200
    assert data["nutrition_plan"]["protein"] == 150.0
    assert data["nutrition_plan"]["carbs"] == 250.0
    assert data["nutrition_plan"]["fat"] == 70.0
    assert data["nutrition_plan"]["fiber"] == 30.0
    assert data["nutrition_plan"]["water_goal"] == 3.0
    assert data["totals"] == {
        "kcal": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
        "fiber": 0.0,
        "water": 2.0,
    }
    assert data["remaining"]["kcal"] == 2200.0
    assert data["remaining"]["protein"] == 150.0
    assert data["remaining"]["carbs"] == 250.0
    assert data["remaining"]["fat"] == 70.0
    assert data["remaining"]["fiber"] == 30.0
    assert data["remaining"]["water"] == 1.0


@pytest.mark.asyncio
async def test_add_macro_log_updates_daily_log_and_recent_foods(
    override_routine_service,
    override_current_user,
    fake_routine_service: FakeRoutineService,
) -> None:
    routine_id = next(iter(fake_routine_service.routines.keys()))
    payload = {
        "meal_type": "BREAKFAST",
        "food_name": "Chicken Breast",
        "amount": 100,
        "amount_unit": "grams",
        "kcal": 165,
        "protein": 31,
        "carbs": 4,
        "fat": 3.6,
        "fiber": 1,
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
    assert add_payload["routine"]["intake_protein"] == 31.0
    assert add_payload["routine"]["intake_carbs"] == 4.0
    assert add_payload["routine"]["intake_fats"] == 3.6
    assert add_payload["routine"]["intake_fiber"] == 1.0
    assert add_payload["routine"]["meals_kcal"] == 165.0

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
        "meal_type": "LUNCH",
        "food_name": "Beef Steak",
        "amount": 250,
        "amount_unit": "grams",
        "kcal": 720,
        "protein": 20,
        "carbs": 45,
        "fat": 30,
        "fiber": 6,
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
    assert data["routine"]["intake_carbs"] == 45.0
    assert data["routine"]["intake_fats"] == 30.0
    assert data["routine"]["intake_fiber"] == 6.0
    assert data["routine"]["meals_kcal"] == 720.0
    assert data["log"]["food_name"] == "Beef Steak"


@pytest.mark.asyncio
async def test_client_updates_and_deletes_logged_meal(
    override_routine_service,
    override_current_user,
    fake_routine_service: FakeRoutineService,
) -> None:
    routine_id = next(iter(fake_routine_service.routines.keys()))
    create_payload = {
        "meal_type": "LUNCH",
        "food_name": "Chicken Bowl",
        "kcal": 600,
        "protein": 45,
        "carbs": 70,
        "fat": 15,
        "fiber": 9,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        create_response = await client.post(
            f"/routines/{routine_id}/macro-logs",
            json=create_payload,
        )
        log_id = create_response.json()["log"]["id"]
        update_response = await client.patch(
            f"/routines/{routine_id}/macro-logs/{log_id}",
            json={
                "kcal": 650,
                "protein": 50,
                "carbs": 72,
                "fat": 17,
                "fiber": 10,
            },
        )
        delete_response = await client.delete(
            f"/routines/{routine_id}/macro-logs/{log_id}",
        )

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert update_response.json()["routine"]["meals_kcal"] == 650.0
    assert update_response.json()["routine"]["intake_protein"] == 50.0
    assert delete_response.status_code == 200
    assert delete_response.json()["meals_kcal"] == 0.0
    assert delete_response.json()["intake_protein"] == 0.0


def test_coach_macro_log_write_route_is_not_exposed() -> None:
    schema = app.openapi()
    coach_log_path = "/coach/clients/{client_id}/routines/today/macro-logs"
    assert coach_log_path not in schema["paths"]


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
    data = response.json()
    assert data["consumed_kcal"] is None
    assert data["goal_kcal"] == 2200.0
    assert data["remaining_kcal"] == 2200.0
    assert data["remaining_protein"] == 150.0
    assert data["remaining_carbs"] == 250.0
    assert data["remaining_fats"] == 70.0
    assert data["remaining_fiber"] == 30.0
    assert data["meals"] == "Chicken and rice"
    assert data["notes"] == "Strong session"


@pytest.mark.asyncio
async def test_self_cannot_override_nutrition_targets_or_log_totals(
    override_routine_service,
    override_current_user,
) -> None:
    payload = {
        "date": "2026-07-01",
        "goal_kcal": 2200.0,
        "meals_kcal": 1000.0,
        "intake_protein": 100.0,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/routines", json=payload)

    assert response.status_code == 422


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
    data = response.json()
    assert data["remaining_kcal"] == 1750.0
    assert data["remaining_protein"] == 70.0
    assert data["remaining_carbs"] == 150.0
    assert data["remaining_fats"] == 40.0
    assert data["remaining_fiber"] == 20.0


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
async def test_patch_routine_tracking_fields_only(
    override_routine_service,
    override_current_user,
    fake_routine_service: FakeRoutineService,
) -> None:
    routine_id = next(iter(fake_routine_service.routines.keys()))

    payload = {
        "meals": "Oats, chicken bowl, yogurt",
        "notes": "Tracked all meals",
        "water_intake": 2.8,
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
    assert data["water_intake"] == 2.8
    assert data["consumed_kcal"] == 450.0
    assert data["remaining_kcal"] == 1750.0


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


@pytest.mark.asyncio
async def test_coach_cannot_use_self_routine_endpoints(
    override_routine_service,
) -> None:
    now = datetime.now(tz=timezone.utc)
    coach = User(
        id=uuid4(),
        email="routine.coach.blocked@example.com",
        hashed_password="hashed-password",
        full_name="Blocked Routine Coach",
        role=UserRole.COACH,
        is_email_verified=True,
        is_active=True,
        use_reference_image=False,
        created_at=now,
        updated_at=now,
    )
    app.dependency_overrides[get_current_user] = lambda: coach
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/routines")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403
    assert response.json()["detail"] == "SELF role required"