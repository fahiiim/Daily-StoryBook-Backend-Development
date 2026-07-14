from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.repositories.user_repository import UserRepository
from app.repositories.verification_code_repository import VerificationCodeRepository
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService, EmailNotVerifiedError
from app.services.email_service import EmailService
from app.services.verification_flow_service import VerificationFlowService
from app.services.verification_service import VerificationService


@pytest.fixture
def sqlite_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_signup_requires_email_otp_verification_before_login(sqlite_session: Session) -> None:
    user_repository = UserRepository(sqlite_session)
    verification_service = VerificationService(VerificationCodeRepository(sqlite_session))
    verification_flow_service = VerificationFlowService(
        user_repository=user_repository,
        verification_service=verification_service,
        email_service=EmailService(),
    )
    auth_service = AuthService(user_repository)

    user = auth_service.register_user(
        RegisterRequest(
            email="signup.verify@example.com",
            password="secret123",
            full_name="Signup Verify User",
            role="SELF",
        )
    )
    otp = verification_flow_service.send_email_verification(current_user=user)

    assert user.is_email_verified is False
    assert len(otp) == 6
    assert otp.isdigit()

    with pytest.raises(EmailNotVerifiedError):
        auth_service.login_user(
            LoginRequest(email="signup.verify@example.com", password="secret123")
        )

    verified_user = verification_flow_service.verify_email_by_email(
        email="signup.verify@example.com",
        code=otp,
    )
    token = auth_service.login_user(
        LoginRequest(email="signup.verify@example.com", password="secret123")
    )

    assert verified_user.is_email_verified is True
    assert token