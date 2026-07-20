from collections.abc import Generator
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.db.database import Base
from app.models.coach_client import CoachClient, CoachClientStatus
from app.models.user import User, UserRole
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.user_repository import UserRepository
from app.schemas.nutrition_plan import NutritionPlanCreate
from app.services.nutrition_plan_service import (
    NutritionPlanAlreadyExistsError,
    NutritionPlanClientNotManagedError,
    NutritionPlanService,
)


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


def _create_user(session: Session, *, email: str, full_name: str, role: UserRole) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("secret123"),
        full_name=full_name,
        role=role,
        is_active=True,
        is_email_verified=True,
        use_reference_image=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _build_service(session: Session) -> NutritionPlanService:
    return NutritionPlanService(
        nutrition_plan_repository=NutritionPlanRepository(session),
        user_repository=UserRepository(session),
        coach_client_repository=CoachClientRepository(session),
    )


def _build_payload(*, client_id, plan_date: date) -> NutritionPlanCreate:
    return NutritionPlanCreate(
        client_id=client_id,
        breakfast="Oats",
        lunch="Rice and chicken",
        dinner="Fish",
        snacks="Fruit",
        daily_calories=2100,
        protein=150,
        carbs=230,
        fat=60,
        water_goal=3.2,
        notes="Week 1",
        date=plan_date,
    )


def test_coach_can_create_same_day_plans_for_different_clients(sqlite_session: Session) -> None:
    coach = _create_user(
        sqlite_session,
        email="nutrition.coach@example.com",
        full_name="Nutrition Coach",
        role=UserRole.COACH,
    )
    first_client = _create_user(
        sqlite_session,
        email="nutrition.client.one@example.com",
        full_name="Nutrition Client One",
        role=UserRole.SELF,
    )
    second_client = _create_user(
        sqlite_session,
        email="nutrition.client.two@example.com",
        full_name="Nutrition Client Two",
        role=UserRole.SELF,
    )
    sqlite_session.add_all(
        [
            CoachClient(
                coach_id=coach.id,
                client_id=first_client.id,
                status=CoachClientStatus.ACCEPTED,
                assign_initial_plan=False,
            ),
            CoachClient(
                coach_id=coach.id,
                client_id=second_client.id,
                status=CoachClientStatus.ACCEPTED,
                assign_initial_plan=False,
            ),
        ]
    )
    sqlite_session.commit()

    service = _build_service(sqlite_session)
    plan_date = date(2026, 7, 19)
    first_plan = service.create_plan(
        current_coach=coach,
        payload=_build_payload(client_id=first_client.id, plan_date=plan_date),
    )
    second_plan = service.create_plan(
        current_coach=coach,
        payload=_build_payload(client_id=second_client.id, plan_date=plan_date),
    )

    assert first_plan.client_id == first_client.id
    assert second_plan.client_id == second_client.id
    assert first_plan.date == second_plan.date


def test_coach_cannot_create_duplicate_same_day_plan_for_same_client(sqlite_session: Session) -> None:
    coach = _create_user(
        sqlite_session,
        email="duplicate.nutrition.coach@example.com",
        full_name="Duplicate Nutrition Coach",
        role=UserRole.COACH,
    )
    client = _create_user(
        sqlite_session,
        email="duplicate.nutrition.client@example.com",
        full_name="Duplicate Nutrition Client",
        role=UserRole.SELF,
    )
    sqlite_session.add(
        CoachClient(
            coach_id=coach.id,
            client_id=client.id,
            status=CoachClientStatus.ACCEPTED,
            assign_initial_plan=False,
        )
    )
    sqlite_session.commit()

    service = _build_service(sqlite_session)
    payload = _build_payload(client_id=client.id, plan_date=date(2026, 7, 19))
    service.create_plan(current_coach=coach, payload=payload)

    with pytest.raises(NutritionPlanAlreadyExistsError):
        service.create_plan(current_coach=coach, payload=payload)


def test_coach_cannot_create_plan_for_pending_client_request(sqlite_session: Session) -> None:
    coach = _create_user(
        sqlite_session,
        email="pending.nutrition.coach@example.com",
        full_name="Pending Nutrition Coach",
        role=UserRole.COACH,
    )
    client = _create_user(
        sqlite_session,
        email="pending.nutrition.client@example.com",
        full_name="Pending Nutrition Client",
        role=UserRole.SELF,
    )
    sqlite_session.add(
        CoachClient(
            coach_id=coach.id,
            client_id=client.id,
            status=CoachClientStatus.PENDING,
            assign_initial_plan=False,
        )
    )
    sqlite_session.commit()

    service = _build_service(sqlite_session)

    with pytest.raises(NutritionPlanClientNotManagedError):
        service.create_plan(
            current_coach=coach,
            payload=_build_payload(client_id=client.id, plan_date=date(2026, 7, 19)),
        )