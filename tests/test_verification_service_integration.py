from datetime import datetime, timedelta, timezone
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.db.database import Base
from app.models.user import User, UserRole
from app.models.verification_code import VerificationCodePurpose
from app.repositories.verification_code_repository import VerificationCodeRepository
from app.services.verification_service import ExpiredVerificationCodeError, VerificationService


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


def _create_user(session: Session) -> User:
    user = User(
        username="verification_integration_user",
        email="verification.integration@example.com",
        hashed_password=hash_password("secret123"),
        full_name="Verification Integration User",
        role=UserRole.SELF,
        is_active=True,
        is_email_verified=False,
        use_reference_image=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_verify_code_handles_naive_sqlite_datetime_and_marks_consumed(sqlite_session: Session) -> None:
    repository = VerificationCodeRepository(sqlite_session)
    service = VerificationService(repository)
    user = _create_user(sqlite_session)

    code = service.generate_code(
        user_id=user.id,
        purpose=VerificationCodePurpose.EMAIL_VERIFICATION,
    )

    latest = repository.get_latest_by_user_and_purpose(
        user_id=user.id,
        purpose=VerificationCodePurpose.EMAIL_VERIFICATION,
    )
    assert latest is not None
    assert latest.code_hash == code

    # Force the exact SQLite-like naive datetime condition that previously crashed verification.
    latest.expires_at = latest.expires_at.replace(tzinfo=None)
    sqlite_session.add(latest)
    sqlite_session.commit()

    service.verify_code(
        user_id=user.id,
        purpose=VerificationCodePurpose.EMAIL_VERIFICATION,
        submitted_code=code,
    )

    refreshed = repository.get_latest_by_user_and_purpose(
        user_id=user.id,
        purpose=VerificationCodePurpose.EMAIL_VERIFICATION,
    )
    assert refreshed is not None
    assert refreshed.consumed_at is not None


def test_verify_code_with_expired_naive_datetime_raises_expired(sqlite_session: Session) -> None:
    repository = VerificationCodeRepository(sqlite_session)
    service = VerificationService(repository)
    user = _create_user(sqlite_session)

    code = service.generate_code(
        user_id=user.id,
        purpose=VerificationCodePurpose.PASSWORD_RESET,
    )

    latest = repository.get_latest_by_user_and_purpose(
        user_id=user.id,
        purpose=VerificationCodePurpose.PASSWORD_RESET,
    )
    assert latest is not None

    expired_naive = (datetime.now(tz=timezone.utc) - timedelta(minutes=1)).replace(tzinfo=None)
    latest.expires_at = expired_naive
    sqlite_session.add(latest)
    sqlite_session.commit()

    with pytest.raises(ExpiredVerificationCodeError):
        service.verify_code(
            user_id=user.id,
            purpose=VerificationCodePurpose.PASSWORD_RESET,
            submitted_code=code,
        )
