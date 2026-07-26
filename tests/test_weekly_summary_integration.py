from collections.abc import Generator
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.db.database import Base
from app.models.coach_client import CoachClient, CoachClientStatus
from app.models.daily_goal import DailyGoalCompletion
from app.models.nutrition_plan import NutritionPlan
from app.models.routine import Routine
from app.models.user import User, UserRole
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.daily_goal_repository import DailyGoalCompletionRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_plan_repository import WorkoutPlanCompletionRepository
from app.services.weekly_summary_service import WeeklySummaryService, build_daily_goal_item_id
from app.services.workout_plan_service import WorkoutPlanService


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


def _build_service(session: Session) -> WeeklySummaryService:
    return WeeklySummaryService(
        routine_repository=RoutineRepository(session),
        workout_plan_repository=WorkoutPlanCompletionRepository(session),
        daily_goal_repository=DailyGoalCompletionRepository(session),
        nutrition_plan_repository=NutritionPlanRepository(session),
    )


def test_current_week_analytics_calculates_daily_and_average_scores(
    sqlite_session: Session,
) -> None:
    coach = _create_user(
        sqlite_session,
        email="analytics.coach@example.com",
        role=UserRole.COACH,
    )
    client = _create_user(
        sqlite_session,
        email="analytics.client@example.com",
        role=UserRole.SELF,
    )
    week_start = date(2026, 7, 20)
    sqlite_session.add(
        CoachClient(
            coach_id=coach.id,
            client_id=client.id,
            status=CoachClientStatus.ACCEPTED,
            assign_initial_plan=False,
        )
    )
    plan = NutritionPlan(
        coach_id=coach.id,
        client_id=client.id,
        date=week_start,
        daily_calories=2000,
        protein=100,
        carbs=200,
        fat=50,
        fiber=20,
        water_goal=3,
        workout_plan=["Do 30 pushups", "Walk for 20 minutes"],
        daily_goals=["Drink enough water", "Sleep for 8 hours"],
    )
    sqlite_session.add(plan)
    sqlite_session.add_all(
        [
            Routine(
                user_id=client.id,
                date=week_start,
                meals_kcal=1000,
                intake_protein=50,
                intake_carbs=100,
                intake_fats=25,
                intake_fiber=10,
                completion_status=False,
            ),
            Routine(
                user_id=client.id,
                date=date(2026, 7, 21),
                meals_kcal=2000,
                intake_protein=100,
                intake_carbs=200,
                intake_fats=50,
                intake_fiber=20,
                completion_status=False,
            ),
        ]
    )
    sqlite_session.commit()
    sqlite_session.refresh(plan)

    completion_repository = WorkoutPlanCompletionRepository(sqlite_session)
    nutrition_repository = NutritionPlanRepository(sqlite_session)
    workout_service = WorkoutPlanService(
        completion_repository=completion_repository,
        nutrition_plan_repository=nutrition_repository,
        user_repository=UserRepository(sqlite_session),
        coach_client_repository=CoachClientRepository(sqlite_session),
    )
    initial_workout = workout_service.get_assigned_plan(
        current_user=client,
        target_date=week_start,
    )
    workout_service.update_completion(
        current_user=client,
        workout_item_id=initial_workout.items[0].id,
        completed=True,
        target_date=week_start,
    )
    workout_service.update_completion(
        current_user=client,
        workout_item_id=initial_workout.items[1].id,
        completed=True,
        target_date=date(2026, 7, 22),
    )

    monday_goal_id = build_daily_goal_item_id(
        nutrition_plan_id=plan.id,
        position=0,
        instruction=plan.daily_goals[0],
    )
    tuesday_goal_ids = [
        build_daily_goal_item_id(
            nutrition_plan_id=plan.id,
            position=position,
            instruction=instruction,
        )
        for position, instruction in enumerate(plan.daily_goals)
    ]
    completed_at = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    sqlite_session.add(
        DailyGoalCompletion(
            nutrition_plan_id=plan.id,
            client_id=client.id,
            goal_item_id=monday_goal_id,
            goal_date=week_start,
            is_completed=True,
            completed_at=completed_at,
        )
    )
    sqlite_session.add_all(
        [
            DailyGoalCompletion(
                nutrition_plan_id=plan.id,
                client_id=client.id,
                goal_item_id=goal_item_id,
                goal_date=date(2026, 7, 21),
                is_completed=True,
                completed_at=completed_at,
            )
            for goal_item_id in tuesday_goal_ids
        ]
    )
    sqlite_session.commit()

    analytics = _build_service(sqlite_session).get_current_week_analytics(
        current_user=client,
        as_of_date=date(2026, 7, 22),
    )

    assert len(analytics.daily_points) == 7
    monday, tuesday, wednesday = analytics.daily_points[:3]
    assert (monday.workout_score, monday.meal_score, monday.daily_goal_score) == (
        50.0,
        50.0,
        50.0,
    )
    assert monday.combined_score == 50.0
    assert (tuesday.workout_score, tuesday.meal_score, tuesday.daily_goal_score) == (
        50.0,
        100.0,
        100.0,
    )
    assert tuesday.combined_score == 83.33
    assert (wednesday.workout_score, wednesday.meal_score, wednesday.daily_goal_score) == (
        100.0,
        0.0,
        0.0,
    )
    assert wednesday.combined_score == 33.33
    assert all(point.is_future for point in analytics.daily_points[3:])
    assert analytics.weekly_averages.workout_score == 66.67
    assert analytics.weekly_averages.meal_score == 50.0
    assert analytics.weekly_averages.daily_goal_score == 50.0
    assert analytics.weekly_averages.combined_score == 55.55
    assert analytics.weekly_averages.ending_workout_completion_rate == 100.0
    assert analytics.coverage.elapsed_days == 3
    assert analytics.coverage.combined_days_scored == 3
    assert analytics.coverage.complete is False


def test_empty_week_returns_seven_null_points(sqlite_session: Session) -> None:
    client = _create_user(
        sqlite_session,
        email="empty.analytics.client@example.com",
        role=UserRole.SELF,
    )

    analytics = _build_service(sqlite_session).get_current_week_analytics(
        current_user=client,
        as_of_date=date(2026, 7, 22),
    )

    assert len(analytics.daily_points) == 7
    assert all(point.combined_score is None for point in analytics.daily_points)
    assert analytics.weekly_averages.combined_score is None
    assert analytics.coverage.combined_days_scored == 0
