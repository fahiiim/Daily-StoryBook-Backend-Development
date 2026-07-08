from datetime import date
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_user
from app.dependencies.onboarding import get_onboarding_service
from app.main import app
from app.models.user import User, UserRole
from app.schemas.onboarding import OnboardingRoleRequest
from app.services.onboarding_service import RoleAlreadySelectedError


class FakeOnboardingService:
    def __init__(self, user: User) -> None:
        self.user = user

    def set_initial_role(self, *, current_user: User, payload: OnboardingRoleRequest) -> User:
        _ = current_user
        if self.user.role is not None:
            raise RoleAlreadySelectedError("Role has already been selected")

        self.user.role = UserRole(payload.role)
        self.user.updated_at = datetime.now(tz=timezone.utc)
        return self.user


@pytest.fixture
def onboarding_user() -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        username="onboarding_user",
        email="onboarding.user@example.com",
        hashed_password="hashed-password",
        full_name="Onboarding User",
        age=None,
        date_of_birth=date(1998, 1, 1),
        gender="female",
        occupation="Engineer",
        fitness_goal="Stay fit",
        bio=None,
        profile_image=None,
        reference_image=None,
        use_reference_image=False,
        role=None,
        is_email_verified=False,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def fake_onboarding_service(onboarding_user: User) -> FakeOnboardingService:
    return FakeOnboardingService(onboarding_user)


@pytest.fixture
def override_onboarding_service(fake_onboarding_service: FakeOnboardingService):
    app.dependency_overrides[get_onboarding_service] = lambda: fake_onboarding_service
    yield
    app.dependency_overrides.pop(get_onboarding_service, None)


@pytest.fixture
def override_current_user(onboarding_user: User):
    app.dependency_overrides[get_current_user] = lambda: onboarding_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_set_onboarding_role_happy_path(override_onboarding_service, override_current_user) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.patch("/onboarding/role", json={"role": "COACH"})

    assert response.status_code == 200
    assert response.json()["role"] == "COACH"


@pytest.mark.asyncio
async def test_set_onboarding_role_rejects_admin_value(
    override_onboarding_service,
    override_current_user,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.patch("/onboarding/role", json={"role": "ADMIN"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_set_onboarding_role_conflict_when_called_twice(
    override_onboarding_service,
    override_current_user,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        first = await client.patch("/onboarding/role", json={"role": "SELF"})
        second = await client.patch("/onboarding/role", json={"role": "COACH"})

    assert first.status_code == 200
    assert second.status_code == 409
