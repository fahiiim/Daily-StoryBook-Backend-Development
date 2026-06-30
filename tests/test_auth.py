from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_auth_service
from app.main import app
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import EmailAlreadyRegisteredError, InvalidCredentialsError


class FakeAuthService:
    def __init__(self) -> None:
        now = datetime.now(tz=timezone.utc)
        self.current_user = User(
            id=uuid4(),
            email="athlete@example.com",
            hashed_password="hashed-password",
            full_name="Athlete User",
            age=28,
            gender="female",
            occupation="Coach",
            fitness_goal="Build endurance",
            profile_image=None,
            reference_image=None,
            role=UserRole.SELF,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def register_user(self, payload: RegisterRequest) -> User:
        if payload.email == "exists@example.com":
            raise EmailAlreadyRegisteredError("Email already registered")

        now = datetime.now(tz=timezone.utc)
        return User(
            id=uuid4(),
            email=payload.email,
            hashed_password="hashed-password",
            full_name=payload.full_name,
            age=payload.age,
            gender=payload.gender,
            occupation=payload.occupation,
            fitness_goal=payload.fitness_goal,
            profile_image=payload.profile_image,
            reference_image=payload.reference_image,
            role=payload.role,
            is_active=payload.is_active,
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
        "email": "newuser@example.com",
        "password": "secret123",
        "full_name": "New User",
        "age": 24,
        "gender": "male",
        "occupation": "Designer",
        "fitness_goal": "Lose fat",
        "profile_image": None,
        "reference_image": None,
        "role": "SELF",
        "is_active": True,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["full_name"] == payload["full_name"]
    assert "hashed_password" not in data


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