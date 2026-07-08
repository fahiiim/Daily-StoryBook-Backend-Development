from datetime import date
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_auth_service
from app.main import app
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.services.auth_service import UsernameAlreadyTakenError


class FakeAuthService:
    def __init__(self) -> None:
        now = datetime.now(tz=timezone.utc)
        self.current_user = User(
            id=uuid4(),
            username="athlete_user",
            email="athlete@example.com",
            hashed_password="hashed-password",
            full_name="Athlete User",
            age=28,
            date_of_birth=date(1996, 1, 1),
            gender="female",
            occupation="Coach",
            fitness_goal="Build endurance",
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

    def register_user(self, payload: RegisterRequest) -> User:
        if payload.email == "exists@example.com":
            raise EmailAlreadyRegisteredError("Email already registered")
        if payload.username == "taken_username":
            raise UsernameAlreadyTakenError("Username already taken")

        now = datetime.now(tz=timezone.utc)
        return User(
            id=uuid4(),
            username=payload.username,
            email=payload.email,
            hashed_password="hashed-password",
            full_name=payload.full_name,
            age=None,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            occupation=payload.occupation,
            fitness_goal=payload.fitness_goal,
            bio=None,
            profile_image=payload.profile_image,
            reference_image=payload.reference_image,
            use_reference_image=False,
            role=None,
            is_email_verified=False,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def login_user(self, payload: LoginRequest) -> str:
        if payload.email != "athlete@example.com" or payload.password != "secret123":
            raise InvalidCredentialsError("Invalid email or password")
        return "valid-token"

    def get_current_user(self, token: str) -> User:
        if token != "valid-token":
            raise InvalidCredentialsError("Invalid token")
        return self.current_user


@pytest.fixture
def fake_auth_service() -> FakeAuthService:
    return FakeAuthService()


@pytest.fixture(autouse=True)
def override_auth_dependency(fake_auth_service: FakeAuthService):
    app.dependency_overrides[get_auth_service] = lambda: fake_auth_service
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_register_endpoint() -> None:
    payload = {
        "username": "new_user_1",
        "email": "newuser@example.com",
        "password": "secret123",
        "full_name": "New User",
        "date_of_birth": "2000-01-01",
        "gender": "male",
        "occupation": "Designer",
        "fitness_goal": "Lose fat",
        "profile_image": None,
        "reference_image": None,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == payload["username"]
    assert data["email"] == payload["email"]
    assert data["full_name"] == payload["full_name"]
    assert data["role"] is None
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_ignores_admin_role_from_payload() -> None:
    payload = {
        "username": "role_escalation_user",
        "email": "escalation@example.com",
        "password": "secret123",
        "full_name": "Escalation Attempt",
        "date_of_birth": "1998-05-20",
        "role": "ADMIN",
        "is_active": False,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["role"] is None
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_rejects_malformed_email() -> None:
    payload = {
        "username": "bad_email_user",
        "email": "not-an-email-at-all",
        "password": "secret123",
        "full_name": "Bad Email",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/register", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_returns_conflict_for_duplicate_username() -> None:
    payload = {
        "username": "taken_username",
        "email": "unique@example.com",
        "password": "secret123",
        "full_name": "Taken Username",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/register", json=payload)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_endpoint() -> None:
    payload = {
        "email": "athlete@example.com",
        "password": "secret123",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/login", json=payload)

    assert response.status_code == 200
    assert response.json() == {"access_token": "valid-token", "token_type": "bearer"}


@pytest.mark.asyncio
async def test_me_endpoint() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/me", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "athlete@example.com"
    assert data["full_name"] == "Athlete User"