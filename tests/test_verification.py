from datetime import date
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.dependencies.auth import get_current_user
from app.dependencies.verification_flow import get_verification_flow_service
from app.main import app
from app.models.user import User, UserRole
from app.services.verification_service import (
    ExpiredVerificationCodeError,
    InvalidVerificationCodeError,
)
from app.services.verification_flow_service import VerificationUserNotFoundError


class FakeVerificationFlowService:
    def __init__(self, user: User) -> None:
        self.user = user
        self.email_code = "111111"
        self.email_code_expired = False
        self.email_code_consumed = False
        self.password_reset_state: dict[str, dict[str, object]] = {}

    def send_email_verification(self, *, current_user: User) -> str:
        _ = current_user
        self.email_code_expired = False
        self.email_code_consumed = False
        return self.email_code

    def send_email_verification_by_email(self, *, email: str) -> str:
        if email.strip().lower() != self.user.email:
            raise VerificationUserNotFoundError("User not found")
        self.email_code_expired = False
        self.email_code_consumed = False
        return self.email_code

    def verify_email(self, *, current_user: User, code: str) -> User:
        _ = current_user
        return self._verify_email(code=code)

    def verify_email_by_email(self, *, email: str, code: str) -> User:
        if email.strip().lower() != self.user.email:
            raise VerificationUserNotFoundError("User not found")
        return self._verify_email(code=code)

    def _verify_email(self, *, code: str) -> User:
        if self.email_code_consumed:
            raise InvalidVerificationCodeError("Verification code has already been used")
        if self.email_code_expired:
            raise ExpiredVerificationCodeError("Verification code has expired")
        if code != self.email_code:
            raise InvalidVerificationCodeError("Invalid verification code")

        self.email_code_consumed = True
        self.user.is_email_verified = True
        self.user.updated_at = datetime.now(tz=timezone.utc)
        return self.user

    def request_password_reset(self, *, email: str) -> str | None:
        if email.strip().lower() != self.user.email:
            return None

        code = "222222"
        self.password_reset_state[self.user.email] = {
            "code": code,
            "expired": False,
            "consumed": False,
        }
        return code

    def reset_password(self, *, email: str, code: str, new_password: str) -> None:
        _ = new_password
        state = self.password_reset_state.get(email.strip().lower())
        if state is None:
            raise InvalidVerificationCodeError("Invalid email or verification code")

        if bool(state["consumed"]):
            raise InvalidVerificationCodeError("Verification code has already been used")
        if bool(state["expired"]):
            raise ExpiredVerificationCodeError("Verification code has expired")
        if str(state["code"]) != code:
            raise InvalidVerificationCodeError("Invalid verification code")

        state["consumed"] = True


@pytest.fixture(autouse=True)
def force_development_env():
    original_env = settings.app_env
    settings.app_env = "development"
    app.openapi_schema = None
    yield
    settings.app_env = original_env
    app.openapi_schema = None


@pytest.fixture
def verification_user() -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        email="verify.user@example.com",
        hashed_password="hashed-password",
        full_name="Verification User",
        age=None,
        date_of_birth=date(1995, 6, 15),
        gender="male",
        occupation="Developer",
        fitness_goal="Consistency",
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
def fake_verification_flow_service(verification_user: User) -> FakeVerificationFlowService:
    return FakeVerificationFlowService(verification_user)


@pytest.fixture
def override_verification_dependencies(
    verification_user: User,
    fake_verification_flow_service: FakeVerificationFlowService,
):
    app.dependency_overrides[get_current_user] = lambda: verification_user
    app.dependency_overrides[get_verification_flow_service] = lambda: fake_verification_flow_service
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_verification_flow_service, None)


@pytest.mark.asyncio
async def test_send_email_verification_includes_raw_otp(override_verification_dependencies) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/email/send-verification",
            json={"email": "verify.user@example.com"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Verification code sent"
    assert payload["otp"] == "111111"


@pytest.mark.asyncio
async def test_send_email_verification_returns_not_found_for_unknown_email(override_verification_dependencies) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/email/send-verification",
            json={"email": "another.user@example.com"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_send_email_verification_requires_email_body(override_verification_dependencies) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/email/send-verification")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_verify_email_happy_path(override_verification_dependencies) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/email/verify",
            json={"email": "verify.user@example.com", "code": "111111"},
        )

    assert response.status_code == 200
    assert response.json()["is_email_verified"] is True


@pytest.mark.asyncio
async def test_verify_email_wrong_code(override_verification_dependencies) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/email/verify",
            json={"email": "verify.user@example.com", "code": "000000"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_expired_code(
    override_verification_dependencies,
    fake_verification_flow_service: FakeVerificationFlowService,
) -> None:
    fake_verification_flow_service.email_code_expired = True

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/email/verify",
            json={"email": "verify.user@example.com", "code": "111111"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_reused_code(override_verification_dependencies) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        payload = {"email": "verify.user@example.com", "code": "111111"}
        first = await client.post("/email/verify", json=payload)
        second = await client.post("/email/verify", json=payload)

    assert first.status_code == 200
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_forgot_password_is_generic_without_otp_for_unknown_email(override_verification_dependencies) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/password/forgot", json={"email": "unknown@example.com"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"].startswith("If an account exists")
    assert "otp" not in payload


@pytest.mark.asyncio
async def test_password_reset_happy_path(override_verification_dependencies, verification_user: User) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        forgot = await client.post("/password/forgot", json={"email": verification_user.email})
        reset = await client.post(
            "/password/reset",
            json={
                "email": verification_user.email,
                "code": forgot.json()["otp"],
                "new_password": "newsecret123",
                "confirm_password": "newsecret123",
            },
        )

    assert forgot.status_code == 200
    assert reset.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_wrong_code(override_verification_dependencies, verification_user: User) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        await client.post("/password/forgot", json={"email": verification_user.email})
        reset = await client.post(
            "/password/reset",
            json={
                "email": verification_user.email,
                "code": "999999",
                "new_password": "newsecret123",
                "confirm_password": "newsecret123",
            },
        )

    assert reset.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_expired_code(
    override_verification_dependencies,
    fake_verification_flow_service: FakeVerificationFlowService,
    verification_user: User,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        forgot = await client.post("/password/forgot", json={"email": verification_user.email})
        fake_verification_flow_service.password_reset_state[verification_user.email]["expired"] = True
        reset = await client.post(
            "/password/reset",
            json={
                "email": verification_user.email,
                "code": forgot.json()["otp"],
                "new_password": "newsecret123",
                "confirm_password": "newsecret123",
            },
        )

    assert reset.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_reused_code(override_verification_dependencies, verification_user: User) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        forgot = await client.post("/password/forgot", json={"email": verification_user.email})
        payload = {
            "email": verification_user.email,
            "code": forgot.json()["otp"],
            "new_password": "newsecret123",
            "confirm_password": "newsecret123",
        }
        first = await client.post("/password/reset", json=payload)
        second = await client.post("/password/reset", json=payload)

    assert first.status_code == 200
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_password_mismatch_returns_422(
    override_verification_dependencies,
    verification_user: User,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/password/reset",
            json={
                "email": verification_user.email,
                "code": "222222",
                "new_password": "newsecret123",
                "confirm_password": "differentsecret123",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_openapi_in_production_does_not_expose_debug_code_field(override_verification_dependencies) -> None:
    original_env = settings.app_env
    settings.app_env = "production"
    app.openapi_schema = None
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/openapi.json")

        assert response.status_code == 200
        assert "debug_code" not in response.text
    finally:
        settings.app_env = original_env
        app.openapi_schema = None


@pytest.mark.asyncio
async def test_openapi_documents_send_verification_body_and_otp_response(
    override_verification_dependencies,
) -> None:
    app.openapi_schema = None
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    operation = schema["paths"]["/email/send-verification"]["post"]
    request_schema_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    response_schema_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]

    assert request_schema_ref.endswith("/EmailVerificationRequest")
    assert response_schema_ref.endswith("/OtpResponse")
    assert "email" in schema["components"]["schemas"]["EmailVerificationRequest"]["required"]
    assert "otp" in schema["components"]["schemas"]["OtpResponse"]["required"]
