from collections.abc import Generator
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.db.database import Base
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegistrationInfoPatchRequest
from app.services.auth_service import AuthService, EmptyRegistrationInfoUpdateError


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


def test_registration_info_update_persists_storybook_generation_fields(sqlite_session: Session) -> None:
    user = User(
        email="registration.info@example.com",
        hashed_password=hash_password("secret123"),
        full_name="Registration Info User",
        role=UserRole.SELF,
        is_active=True,
        is_email_verified=True,
        use_reference_image=False,
    )
    sqlite_session.add(user)
    sqlite_session.commit()
    sqlite_session.refresh(user)

    service = AuthService(UserRepository(sqlite_session))
    updated = service.update_registration_info(
        current_user=user,
        payload=RegistrationInfoPatchRequest(
            full_name="Story Ready User",
            date_of_birth=date(1997, 7, 14),
            gender="female",
            occupation="Designer",
            fitness_goal="Build endurance",
            wake_up_time="05:45",
            bed_time="22:15",
            height="170 cm",
            weight=67.5,
            target_weight=63.0,
            short_bio="A runner building a better routine.",
            fitness_motivation="Keep energy high for family and work.",
        ),
    )
    sqlite_session.refresh(updated)

    assert updated.full_name == "Story Ready User"
    assert updated.age is None
    assert updated.date_of_birth == date(1997, 7, 14)
    assert updated.gender == "female"
    assert updated.occupation == "Designer"
    assert updated.fitness_goal == "Build endurance"
    assert updated.wake_up_time == "05:45"
    assert updated.bed_time == "22:15"
    assert updated.height == "170 cm"
    assert updated.weight == 67.5
    assert updated.target_weight == 63.0
    assert updated.short_bio == "A runner building a better routine."
    assert updated.fitness_motivation == "Keep energy high for family and work."


def test_registration_info_update_rejects_empty_payload(sqlite_session: Session) -> None:
    user = User(
        email="registration.info.empty@example.com",
        hashed_password=hash_password("secret123"),
        full_name="Registration Info Empty User",
        role=UserRole.SELF,
        is_active=True,
        is_email_verified=True,
        use_reference_image=False,
    )
    sqlite_session.add(user)
    sqlite_session.commit()
    sqlite_session.refresh(user)

    service = AuthService(UserRepository(sqlite_session))

    with pytest.raises(EmptyRegistrationInfoUpdateError):
        service.update_registration_info(
            current_user=user,
            payload=RegistrationInfoPatchRequest(),
        )