from collections.abc import Generator
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.db.database import Base
from app.models.coach_client import CoachClient, CoachClientStatus
from app.models.nutrition_plan import NutritionPlan
from app.models.user import User, UserRole
from app.models.workout_plan import WorkoutPlan, WorkoutPlanAssignment
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.storybook_repository import StorybookRepository
from app.repositories.user_repository import UserRepository
from app.repositories.weekly_summary_repository import WeeklySummaryRepository
from app.repositories.workout_plan_repository import WorkoutPlanRepository
from app.schemas.ai import WeeklySummaryGenerateRequest
from app.services.weekly_summary_service import WeeklySummaryService


class CapturingAIService:
    def __init__(self) -> None:
        self.calls = 0
        self.payload: WeeklySummaryGenerateRequest | None = None

    async def generate_weekly_summary(
        self,
        *,
        payload: WeeklySummaryGenerateRequest,
    ) -> dict[str, object]:
        self.calls += 1
        self.payload = payload
        return {"summary": "A complete client-wide weekly summary"}


@pytest.fixture
def sqlite_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _create_user(session: Session, *, email: str, role: UserRole) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("secret123"),
        full_name=email.split("@", 1)[0],
        role=role,
        is_active=True,
        is_email_verified=True,
        use_reference_image=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_weekly_summary_persists_new_plan_fields_without_nested_transaction(
    sqlite_session: Session,
) -> None:
    coach = _create_user(
        sqlite_session,
        email="weekly.integration.coach@example.com",
        role=UserRole.COACH,
    )
    client = _create_user(
        sqlite_session,
        email="weekly.integration.client@example.com",
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
    sqlite_session.add(
        NutritionPlan(
            coach_id=coach.id,
            client_id=client.id,
            date=date.today(),
            daily_calories=2100,
            protein=150,
            carbs=230,
            fat=60,
            fiber=28,
            water_goal=3.2,
            workout_plan=["Do 30 pushups", "Walk for 20 minutes"],
            daily_goals=["Drink enough water", "Sleep for 8 hours"],
        )
    )
    workout_plan = WorkoutPlan(
        coach_id=coach.id,
        title="Weekly strength plan",
        exercises=["Do 30 pushups", "Do 50 squats"],
        is_active=True,
    )
    sqlite_session.add(workout_plan)
    sqlite_session.flush()
    sqlite_session.add(
        WorkoutPlanAssignment(
            plan_id=workout_plan.id,
            client_id=client.id,
            assigned_by_coach_id=coach.id,
        )
    )
    sqlite_session.commit()

    ai_service = CapturingAIService()
    weekly_summary_repository = WeeklySummaryRepository(sqlite_session)
    service = WeeklySummaryService(
        db=sqlite_session,
        ai_service=ai_service,  # type: ignore[arg-type]
        weekly_summary_repository=weekly_summary_repository,
        routine_repository=RoutineRepository(sqlite_session),
        workout_plan_repository=WorkoutPlanRepository(sqlite_session),
        nutrition_plan_repository=NutritionPlanRepository(sqlite_session),
        storybook_repository=StorybookRepository(sqlite_session),
        user_repository=UserRepository(sqlite_session),
        coach_client_repository=CoachClientRepository(sqlite_session),
    )

    summary = await service.generate_weekly_summary(current_user=client)
    cached_summary = await service.generate_weekly_summary(current_user=client)

    assert summary.id == cached_summary.id
    assert ai_service.calls == 1
    assert ai_service.payload is not None
    assert ai_service.payload.workout_plans[0]["exercises"] == [
        "Do 30 pushups",
        "Do 50 squats",
    ]
    assert ai_service.payload.nutrition_plans[0]["fiber"] == 28.0
    assert ai_service.payload.nutrition_plans[0]["workout_plan"] == [
        "Do 30 pushups",
        "Walk for 20 minutes",
    ]
    assert ai_service.payload.nutrition_plans[0]["daily_goals"] == [
        "Drink enough water",
        "Sleep for 8 hours",
    ]
    assert weekly_summary_repository.get_by_user_and_week_start(
        user_id=client.id,
        week_start=summary.week_start,
    ) is not None
