from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_coach, get_current_user
from app.dependencies.nutrition_plan import get_nutrition_plan_service
from app.main import app
from app.models.nutrition_plan import NutritionPlan
from app.models.user import User, UserRole
from app.schemas.nutrition_plan import NutritionPlanCreate, NutritionPlanPut
from app.services.nutrition_plan_service import (
    NutritionPlanClientNotFoundError,
    NutritionPlanClientNotManagedError,
    NutritionPlanNotFoundError,
)


class FakeNutritionPlanService:
    def __init__(self, *, coach_user: User, managed_client: User, unmanaged_client: User) -> None:
        self.coach_user = coach_user
        self.managed_client = managed_client
        self.unmanaged_client = unmanaged_client
        self.clients = {
            managed_client.id: managed_client,
            unmanaged_client.id: unmanaged_client,
        }
        self.managed_client_ids = {managed_client.id}

        now = datetime.now(tz=timezone.utc)
        initial_plan = NutritionPlan(
            id=uuid4(),
            coach_id=coach_user.id,
            client_id=managed_client.id,
            daily_calories=2200,
            protein=160,
            carbs=220,
            fat=70,
            fiber=30,
            water_goal=3.0,
            workout_plan=["Do 30 pushups", "Walk for 20 minutes"],
            daily_goals=["Drink 3 litres of water", "Sleep for 8 hours"],
            notes="Initial phase",
            date=date(2026, 7, 1),
            created_at=now,
            updated_at=now,
        )
        self.plans = {initial_plan.id: initial_plan}

    def create_plan(self, *, current_coach: User, payload: NutritionPlanCreate) -> NutritionPlan:
        if payload.client_id not in self.clients:
            raise NutritionPlanClientNotFoundError("Client not found")
        if payload.client_id not in self.managed_client_ids:
            raise NutritionPlanClientNotManagedError("Client is not assigned to this coach")

        now = datetime.now(tz=timezone.utc)
        plan = NutritionPlan(
            id=uuid4(),
            coach_id=current_coach.id,
            client_id=payload.client_id,
            daily_calories=payload.daily_calories,
            protein=payload.protein,
            carbs=payload.carbs,
            fat=payload.fat,
            fiber=payload.fiber,
            water_goal=payload.water_goal,
            workout_plan=list(payload.workout_plan),
            daily_goals=list(payload.daily_goals),
            notes=payload.notes,
            date=payload.date,
            created_at=now,
            updated_at=now,
        )
        self.plans[plan.id] = plan
        return plan

    def list_viewable_plans(self, *, current_user: User) -> list[NutritionPlan]:
        if current_user.role == UserRole.COACH:
            return [plan for plan in self.plans.values() if plan.coach_id == current_user.id]
        return [plan for plan in self.plans.values() if plan.client_id == current_user.id]

    def get_viewable_plan(self, *, current_user: User, plan_id) -> NutritionPlan:
        plan = self.plans.get(plan_id)
        if plan is None:
            raise NutritionPlanNotFoundError("Nutrition plan not found")

        if current_user.role == UserRole.COACH and plan.coach_id == current_user.id:
            return plan

        if current_user.role != UserRole.COACH and plan.client_id == current_user.id:
            return plan

        raise NutritionPlanNotFoundError("Nutrition plan not found")

    def replace_plan(self, *, current_coach: User, plan_id, payload: NutritionPlanPut) -> NutritionPlan:
        plan = self.plans.get(plan_id)
        if plan is None or plan.coach_id != current_coach.id:
            raise NutritionPlanNotFoundError("Nutrition plan not found")
        if payload.client_id not in self.clients:
            raise NutritionPlanClientNotFoundError("Client not found")
        if payload.client_id not in self.managed_client_ids:
            raise NutritionPlanClientNotManagedError("Client is not assigned to this coach")

        updates = payload.model_dump()
        for field_name, value in updates.items():
            setattr(plan, field_name, value)
        plan.updated_at = datetime.now(tz=timezone.utc)
        return plan

    def delete_plan(self, *, current_coach: User, plan_id) -> None:
        plan = self.plans.get(plan_id)
        if plan is None or plan.coach_id != current_coach.id:
            raise NutritionPlanNotFoundError("Nutrition plan not found")
        del self.plans[plan_id]


def _build_user(*, role: UserRole, email: str, full_name: str) -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        email=email,
        hashed_password="hashed-password",
        full_name=full_name,
        age=None,
        date_of_birth=date(1996, 6, 6),
        gender="male",
        occupation="Trainer",
        fitness_goal="Maintain",
        bio=None,
        profile_image=None,
        reference_image=None,
        use_reference_image=False,
        role=role,
        is_email_verified=False,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def coach_user() -> User:
    return _build_user(role=UserRole.COACH, email="coach.nutri@example.com", full_name="Coach Nutri")


@pytest.fixture
def managed_client() -> User:
    return _build_user(role=UserRole.SELF, email="client.managed@example.com", full_name="Managed Client")


@pytest.fixture
def unmanaged_client() -> User:
    return _build_user(role=UserRole.SELF, email="client.unmanaged@example.com", full_name="Unmanaged Client")


@pytest.fixture
def fake_nutrition_plan_service(
    coach_user: User,
    managed_client: User,
    unmanaged_client: User,
) -> FakeNutritionPlanService:
    return FakeNutritionPlanService(
        coach_user=coach_user,
        managed_client=managed_client,
        unmanaged_client=unmanaged_client,
    )


@pytest.fixture
def override_nutrition_plan_service(fake_nutrition_plan_service: FakeNutritionPlanService):
    app.dependency_overrides[get_nutrition_plan_service] = lambda: fake_nutrition_plan_service
    yield
    app.dependency_overrides.pop(get_nutrition_plan_service, None)


@pytest.fixture
def override_current_coach(coach_user: User):
    app.dependency_overrides[get_current_coach] = lambda: coach_user
    yield
    app.dependency_overrides.pop(get_current_coach, None)


@pytest.fixture
def override_current_user_coach(coach_user: User):
    app.dependency_overrides[get_current_user] = lambda: coach_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def override_current_user_managed_client(managed_client: User):
    app.dependency_overrides[get_current_user] = lambda: managed_client
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def override_current_user_unmanaged_client(unmanaged_client: User):
    app.dependency_overrides[get_current_user] = lambda: unmanaged_client
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_coach_create_nutrition_plan(
    override_nutrition_plan_service,
    override_current_coach,
    managed_client: User,
) -> None:
    payload = {
        "client_id": str(managed_client.id),
        "daily_calories": 2100,
        "protein": 150,
        "carbs": 230,
        "fat": 60,
        "fiber": 28,
        "water_goal": 3.2,
        "workout_plan": [f"Exercise instruction {index}" for index in range(150)],
        "daily_goals": [f"Daily goal {index}" for index in range(150)],
        "notes": "Week 1",
        "date": "2026-07-02",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/coach/nutrition-plans", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["daily_calories"] == 2100
    assert data["fiber"] == 28.0
    assert len(data["workout_plan"]) == 150
    assert len(data["daily_goals"]) == 150
    assert "breakfast" not in data
    assert "lunch" not in data
    assert "dinner" not in data
    assert "snacks" not in data


@pytest.mark.asyncio
async def test_coach_list_nutrition_plans(
    override_nutrition_plan_service,
    override_current_user_coach,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/coach/nutrition-plans")

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_coach_get_nutrition_plan(
    override_nutrition_plan_service,
    override_current_user_coach,
    fake_nutrition_plan_service: FakeNutritionPlanService,
) -> None:
    plan_id = next(iter(fake_nutrition_plan_service.plans.keys()))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"/coach/nutrition-plans/{plan_id}")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_coach_update_nutrition_plan(
    override_nutrition_plan_service,
    override_current_coach,
    fake_nutrition_plan_service: FakeNutritionPlanService,
    managed_client: User,
) -> None:
    plan_id = next(iter(fake_nutrition_plan_service.plans.keys()))
    payload = {
        "client_id": str(managed_client.id),
        "daily_calories": 2300,
        "protein": 170,
        "carbs": 240,
        "fat": 65,
        "fiber": 32,
        "water_goal": 3.5,
        "workout_plan": ["Do 40 pushups", "Do 60 squats"],
        "daily_goals": ["Take 10,000 steps", "Prepare tomorrow's meals"],
        "notes": "Adjusted",
        "date": "2026-07-03",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.put(f"/coach/nutrition-plans/{plan_id}", json=payload)

    assert response.status_code == 200
    assert response.json()["fiber"] == 32.0
    assert response.json()["workout_plan"] == ["Do 40 pushups", "Do 60 squats"]
    assert response.json()["daily_goals"] == [
        "Take 10,000 steps",
        "Prepare tomorrow's meals",
    ]


@pytest.mark.asyncio
async def test_coach_delete_nutrition_plan(
    override_nutrition_plan_service,
    override_current_coach,
    fake_nutrition_plan_service: FakeNutritionPlanService,
) -> None:
    plan_id = next(iter(fake_nutrition_plan_service.plans.keys()))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.delete(f"/coach/nutrition-plans/{plan_id}")

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_client_only_views_own_assigned(
    override_nutrition_plan_service,
    override_current_user_managed_client,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/coach/nutrition-plans")

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_client_cannot_view_other_client_plan(
    override_nutrition_plan_service,
    override_current_user_unmanaged_client,
    fake_nutrition_plan_service: FakeNutritionPlanService,
) -> None:
    plan_id = next(iter(fake_nutrition_plan_service.plans.keys()))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"/coach/nutrition-plans/{plan_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_client_cannot_create_nutrition_plan(
    override_nutrition_plan_service,
    override_current_user_managed_client,
    managed_client: User,
) -> None:
    payload = {
        "client_id": str(managed_client.id),
        "daily_calories": 2000,
        "protein": 120,
        "carbs": 200,
        "fat": 55,
        "fiber": 25,
        "water_goal": 2.5,
        "workout_plan": ["Blocked workout"],
        "daily_goals": ["Blocked goal"],
        "notes": "Blocked",
        "date": "2026-07-05",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/coach/nutrition-plans", json=payload)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_coach_meal_fields_are_rejected(
    override_nutrition_plan_service,
    override_current_coach,
    managed_client: User,
) -> None:
    payload = {
        "client_id": str(managed_client.id),
        "breakfast": "Coach-authored meal",
        "date": "2026-07-06",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/coach/nutrition-plans", json=payload)

    assert response.status_code == 422


def test_openapi_documents_new_plan_collections_and_no_coach_meals() -> None:
    schema = app.openapi()
    nutrition_properties = schema["components"]["schemas"]["NutritionPlanCreate"]["properties"]
    workout_properties = schema["components"]["schemas"]["WorkoutPlanCreate"]["properties"]
    workout_patch_properties = schema["components"]["schemas"]["WorkoutPlanPatch"]["properties"]

    assert {"fiber", "workout_plan", "daily_goals"} <= nutrition_properties.keys()
    assert nutrition_properties["workout_plan"]["type"] == "array"
    assert nutrition_properties["daily_goals"]["type"] == "array"
    assert not {"breakfast", "lunch", "dinner", "snacks"} & nutrition_properties.keys()
    assert workout_properties["exercises"]["type"] == "array"
    assert workout_patch_properties["title"]["type"] == "string"
    assert workout_patch_properties["exercises"]["type"] == "array"
    assert workout_patch_properties["is_active"]["type"] == "boolean"