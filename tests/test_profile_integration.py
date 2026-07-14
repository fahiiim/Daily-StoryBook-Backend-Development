from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password, verify_password
from app.db.database import Base
from app.models.coach_client import CoachClient
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User, UserRole
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.profile import CoachSettingsUpdateRequest, PasswordUpdateRequest
from app.services.profile_service import InvalidCurrentPasswordError, ProfileService


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


def _build_profile_service(session: Session) -> ProfileService:
    return ProfileService(
        user_repository=UserRepository(session),
        subscription_repository=SubscriptionRepository(session),
        coach_client_repository=CoachClientRepository(session),
    )


def test_self_profile_includes_current_subscription_plan(sqlite_session: Session) -> None:
    user = User(
        email="self.profile.integration@example.com",
        hashed_password=hash_password("secret123"),
        full_name="Self Profile Integration",
        role=UserRole.SELF,
        is_active=True,
        is_email_verified=True,
        use_reference_image=False,
    )
    sqlite_session.add(user)
    sqlite_session.commit()
    sqlite_session.refresh(user)

    subscription = Subscription(
        user_id=user.id,
        plan_name="Premium",
        status=SubscriptionStatus.ACTIVE,
    )
    sqlite_session.add(subscription)
    sqlite_session.commit()

    profile = _build_profile_service(sqlite_session).get_self_profile(user)

    assert profile.name == "Self Profile Integration"
    assert profile.subscription_plan is not None
    assert profile.subscription_plan.plan_name == "Premium"


def test_coach_settings_limits_and_password_update(sqlite_session: Session) -> None:
    coach = User(
        email="coach.profile.integration@example.com",
        hashed_password=hash_password("oldsecret123"),
        full_name="Coach Profile Integration",
        role=UserRole.COACH,
        phone_number="+15550001111",
        max_client_capacity=3,
        is_active=True,
        is_email_verified=True,
        use_reference_image=False,
    )
    first_client = User(
        email="coach.limit.one@example.com",
        hashed_password=hash_password("secret123"),
        full_name="Coach Limit One",
        role=UserRole.SELF,
        is_active=True,
        is_email_verified=True,
        use_reference_image=False,
    )
    second_client = User(
        email="coach.limit.two@example.com",
        hashed_password=hash_password("secret123"),
        full_name="Coach Limit Two",
        role=UserRole.SELF,
        is_active=True,
        is_email_verified=True,
        use_reference_image=False,
    )
    sqlite_session.add_all([coach, first_client, second_client])
    sqlite_session.commit()
    sqlite_session.refresh(coach)
    sqlite_session.refresh(first_client)
    sqlite_session.refresh(second_client)
    sqlite_session.add_all(
        [
            CoachClient(coach_id=coach.id, client_id=first_client.id),
            CoachClient(coach_id=coach.id, client_id=second_client.id),
        ]
    )
    sqlite_session.commit()

    service = _build_profile_service(sqlite_session)
    settings = service.update_coach_settings(
        coach,
        CoachSettingsUpdateRequest(
            name="Updated Coach Integration",
            phone_number="+15552223333",
            bio="Updated biography",
        ),
    )
    limits = service.get_coach_client_management_limits(coach)

    assert settings.name == "Updated Coach Integration"
    assert settings.phone_number == "+15552223333"
    assert settings.bio == "Updated biography"
    assert limits.max_client_capacity == 3
    assert limits.current_clients == 2
    assert limits.remaining_client_capacity == 1

    with pytest.raises(InvalidCurrentPasswordError):
        service.update_coach_password(
            coach,
            PasswordUpdateRequest(
                current_password="wrongsecret",
                new_password="newsecret123",
                confirm_password="newsecret123",
            ),
        )

    service.update_coach_password(
        coach,
        PasswordUpdateRequest(
            current_password="oldsecret123",
            new_password="newsecret123",
            confirm_password="newsecret123",
        ),
    )
    sqlite_session.refresh(coach)

    assert verify_password("newsecret123", coach.hashed_password)