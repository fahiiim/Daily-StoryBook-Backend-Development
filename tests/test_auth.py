from datetime import date
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_auth_service
from app.dependencies.verification_flow import get_verification_flow_service
from app.main import app
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, RegistrationInfoPatchRequest
from app.services.auth_service import EmailAlreadyRegisteredError, EmailNotVerifiedError, InvalidCredentialsError
from app.services.auth_service import EmptyRegistrationInfoUpdateError


class FakeAuthService:
    def __init__(self) -> None:
        now = datetime.now(tz=timezone.utc)
        self.current_user = User(
            id=uuid4(),
            email="athlete@example.com",
            hashed_password="hashed-password",
            full_name="Athlete User",
            age=28,
            date_of_birth=date(1996, 1, 1),
            gender="female",
            occupation="Coach",
            fitness_goal="Build endurance",
            wake_up_time=None,
            bed_time=None,
            height=None,
            weight=None,
            target_weight=None,
            short_bio=None,
            fitness_motivation=None,
            bio=None,
            profile_image=None,
            reference_image=None,
            use_reference_image=False,
            role=UserRole.SELF,
            is_email_verified=True,
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
            age=None,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            occupation=payload.occupation,
            fitness_goal=payload.fitness_goal,
            wake_up_time=payload.wake_up_time,
            bed_time=payload.bed_time,
            height=payload.height,
            weight=payload.weight,
            target_weight=payload.target_weight,
            short_bio=payload.short_bio,
            fitness_motivation=payload.fitness_motivation,
            bio=None,
            profile_image=payload.profile_image,
            reference_image=payload.reference_image,
            use_reference_image=False,
            role=UserRole(payload.role),
            is_email_verified=False,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def login_user(self, payload: LoginRequest) -> str:
        if payload.email == "unverified@example.com":
            raise EmailNotVerifiedError("Email is not verified")
        if payload.email != "athlete@example.com" or payload.password != "secret123":
            raise InvalidCredentialsError("Invalid email or password")
        return "valid-token"

    def get_current_user(self, token: str) -> User:
        if token != "valid-token":
            raise InvalidCredentialsError("Invalid token")
        return self.current_user

    def update_registration_info(self, *, current_user: User, payload: RegistrationInfoPatchRequest) -> User:
        _ = current_user
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise EmptyRegistrationInfoUpdateError("No registration information fields were provided")

        for field_name, value in updates.items():
            setattr(self.current_user, field_name, value)
        self.current_user.updated_at = datetime.now(tz=timezone.utc)
        return self.current_user


class FakeVerificationFlowService:
    def send_email_verification(self, *, current_user: User) -> str:
        _ = current_user
        return "111111"


@pytest.fixture
def fake_auth_service() -> FakeAuthService:
    return FakeAuthService()


@pytest.fixture
def fake_verification_flow_service() -> FakeVerificationFlowService:
    return FakeVerificationFlowService()


@pytest.fixture(autouse=True)
def override_auth_dependency(
    fake_auth_service: FakeAuthService,
    fake_verification_flow_service: FakeVerificationFlowService,
):
    app.dependency_overrides[get_auth_service] = lambda: fake_auth_service
    app.dependency_overrides[get_verification_flow_service] = lambda: fake_verification_flow_service
    yield
    app.dependency_overrides.clear()


def test_openapi_uses_token_only_bearer_authorization() -> None:
    app.openapi_schema = None
    schema = app.openapi()
    security_schemes = schema["components"]["securitySchemes"]

    assert "BearerAuth" in security_schemes
    assert security_schemes["BearerAuth"]["type"] == "http"
    assert security_schemes["BearerAuth"]["scheme"] == "bearer"
    assert "flows" not in security_schemes["BearerAuth"]
    assert "OAuth2PasswordBearer" not in security_schemes
    assert "/onboarding/role" not in schema["paths"]


@pytest.mark.asyncio
async def test_register_endpoint() -> None:
    payload = {
        "email": "newuser@example.com",
        "password": "secret123",
        "full_name": "New User",
        "role": "SELF",
        "date_of_birth": "2000-01-01",
        "gender": "male",
        "occupation": "Designer",
        "fitness_goal": "Lose fat",
        "wake_up_time": "06:00",
        "bed_time": "22:30",
        "height": "175 cm",
        "weight": 78.5,
        "target_weight": 72.0,
        "short_bio": "New user short bio",
        "fitness_motivation": "Have more energy",
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
    assert "otp" not in data
    assert data["user"]["email"] == payload["email"]
    assert data["user"]["full_name"] == payload["full_name"]
    assert data["user"]["role"] == "SELF"
    assert data["user"]["age"] == 26
    assert data["user"]["wake_up_time"] == "06:00"
    assert data["user"]["bed_time"] == "22:30"
    assert data["user"]["height"] == "175 cm"
    assert data["user"]["weight"] == 78.5
    assert data["user"]["target_weight"] == 72.0
    assert data["user"]["short_bio"] == "New user short bio"
    assert data["user"]["fitness_motivation"] == "Have more energy"
    assert data["user"]["is_email_verified"] is False
    assert "hashed_password" not in data["user"]


@pytest.mark.asyncio
async def test_register_rejects_admin_role_from_payload() -> None:
    payload = {
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

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_requires_role() -> None:
    payload = {
        "email": "missing.role@example.com",
        "password": "secret123",
        "full_name": "Missing Role",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/register", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_malformed_email() -> None:
    payload = {
        "email": "not-an-email-at-all",
        "password": "secret123",
        "full_name": "Bad Email",
        "role": "SELF",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/register", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_returns_conflict_for_duplicate_email() -> None:
    payload = {
        "email": "exists@example.com",
        "password": "secret123",
        "full_name": "Existing Email",
        "role": "COACH",
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
async def test_login_rejects_unverified_email() -> None:
    payload = {
        "email": "unverified@example.com",
        "password": "secret123",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/login", json=payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "Verify your email before logging in"


@pytest.mark.asyncio
async def test_patch_registration_info_updates_storybook_fields() -> None:
    payload = {
        "full_name": "Updated Athlete",
        "date_of_birth": "1996-07-14",
        "gender": "female",
        "fitness_goal": "Build strength",
        "wake_up_time": "06:00",
        "bed_time": "22:30",
        "height": "5ft 7in",
        "weight": 68.5,
        "target_weight": 64.0,
        "short_bio": "Training for a better daily story.",
        "fitness_motivation": "Feel strong and consistent.",
        "profile_image": "https://example.com/profile.jpg",
        "reference_image": "https://example.com/reference.jpg",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.patch(
            "/auth/registration-info",
            json=payload,
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    user = response.json()["user"]
    assert user["full_name"] == "Updated Athlete"
    assert user["age"] == 30
    assert user["date_of_birth"] == "1996-07-14"
    assert user["gender"] == "female"
    assert user["fitness_goal"] == "Build strength"
    assert user["wake_up_time"] == "06:00"
    assert user["bed_time"] == "22:30"
    assert user["height"] == "5ft 7in"
    assert user["weight"] == 68.5
    assert user["target_weight"] == 64.0
    assert user["short_bio"] == "Training for a better daily story."
    assert user["fitness_motivation"] == "Feel strong and consistent."
    assert user["profile_image"] == "https://example.com/profile.jpg"
    assert user["reference_image"] == "https://example.com/reference.jpg"


@pytest.mark.asyncio
async def test_patch_registration_info_rejects_empty_payload() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.patch(
            "/auth/registration-info",
            json={},
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 400


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