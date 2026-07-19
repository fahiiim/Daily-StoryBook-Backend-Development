from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.db.database import Base
from app.models.coach_client import CoachClient, CoachClientStatus
from app.models.nutrition_plan import NutritionPlan
from app.models.routine_macro_log import MacroType, MealType
from app.models.user import User, UserRole
from app.repositories.routine_repository import RoutineRepository
from app.schemas.routine import RoutineCreate, RoutineMacroLogCreate, RoutinePatch, RoutineRead
from app.services.routine_service import RoutineClientNotManagedError, RoutineService


def _create_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def _create_user(
    session: Session,
    *,
    email: str = "macro.integration@example.com",
    full_name: str = "Macro Integration User",
    role: UserRole = UserRole.SELF,
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("secret123"),
        full_name=full_name,
        date_of_birth=date(1998, 1, 1),
        role=role,
        is_active=True,
        is_email_verified=False,
        use_reference_image=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_routine_macro_goals_and_consumed_kcal_calculation() -> None:
    session = _create_session()
    try:
        user = _create_user(session)
        service = RoutineService(RoutineRepository(session))

        routine = service.create_routine(
            current_user=user,
            payload=RoutineCreate(
                date=date(2026, 7, 10),
                meals="Oats and chicken",
                meals_kcal=1580,
                intake_protein=100,
                intake_carbs=120,
                intake_fats=40,
                intake_fiber=20,
                notes="All meals tracked",
                completion_status=False,
            ),
        )

        read_model = RoutineRead.model_validate(routine)

        assert read_model.consumed_kcal == 1580.0
        assert read_model.remaining_kcal is None
        assert read_model.remaining_protein is None
        assert read_model.remaining_carbs is None
        assert read_model.remaining_fats is None
        assert read_model.remaining_fiber is None
        assert read_model.meals == "Oats and chicken"
        assert read_model.notes == "All meals tracked"
    finally:
        session.close()


def test_routine_goals_are_derived_from_nutrition_plan() -> None:
    session = _create_session()
    try:
        coach = _create_user(
            session,
            email="macro.goal.coach@example.com",
            full_name="Macro Goal Coach",
            role=UserRole.COACH,
        )
        user = _create_user(
            session,
            email="macro.goal.client@example.com",
            full_name="Macro Goal Client",
            role=UserRole.SELF,
        )
        session.add(
            NutritionPlan(
                coach_id=coach.id,
                client_id=user.id,
                daily_calories=2200,
                protein=150,
                carbs=250,
                fat=70,
                date=date(2026, 7, 10),
            )
        )
        session.commit()

        service = RoutineService(RoutineRepository(session))
        routine = service.create_routine(
            current_user=user,
            payload=RoutineCreate(
                date=date(2026, 7, 10),
                meals_kcal=1580,
                intake_protein=100,
                intake_carbs=120,
                intake_fats=40,
                intake_fiber=20,
                completion_status=False,
            ),
        )
        routine = service.apply_nutrition_goals(
            routine=routine,
            client_id=user.id,
            routine_date=date(2026, 7, 10),
        )
        read_model = RoutineRead.model_validate(routine)

        assert read_model.goal_kcal == 2200.0
        assert read_model.goal_protein == 150.0
        assert read_model.goal_carbs == 250.0
        assert read_model.goal_fats == 70.0
        assert read_model.goal_fiber is None
        assert read_model.remaining_kcal == 620.0
        assert read_model.remaining_protein == 50.0
        assert read_model.remaining_carbs == 130.0
        assert read_model.remaining_fats == 30.0
        assert read_model.remaining_fiber is None
    finally:
        session.close()


def test_coach_adds_logged_meal_for_accepted_client() -> None:
    session = _create_session()
    try:
        coach = _create_user(
            session,
            email="routine.coach@example.com",
            full_name="Routine Coach",
            role=UserRole.COACH,
        )
        client = _create_user(
            session,
            email="routine.client@example.com",
            full_name="Routine Client",
            role=UserRole.SELF,
        )
        session.add(
            CoachClient(
                coach_id=coach.id,
                client_id=client.id,
                status=CoachClientStatus.ACCEPTED,
                assign_initial_plan=False,
            )
        )
        session.commit()

        service = RoutineService(RoutineRepository(session))
        routine = service.get_or_create_client_routine_for_date(
            current_coach=coach,
            client_id=client.id,
            target_date=date(2026, 7, 13),
        )
        updated_routine, log = service.add_client_macro_log(
            current_coach=coach,
            client_id=client.id,
            target_date=date(2026, 7, 13),
            payload=RoutineMacroLogCreate(
                macro_type=MacroType.CARBS,
                meal_type=MealType.LUNCH,
                food_name="Mediterranean Bowl",
                macro_grams=45,
                kcal=420,
                logged_at=datetime(2026, 7, 13, 12, 45, tzinfo=timezone.utc),
            ),
        )
        logs = service.list_client_macro_logs(
            current_coach=coach,
            client_id=client.id,
            routine_id=routine.id,
        )

        assert routine.user_id == client.id
        assert updated_routine.intake_carbs == 45.0
        assert updated_routine.meals_kcal == 420.0
        assert log.meal_type == MealType.LUNCH
        assert log.amount == 1.0
        assert log.amount_unit == "serving"
        assert [item.food_name for item in logs] == ["Mediterranean Bowl"]
    finally:
        session.close()


def test_coach_cannot_add_logged_meal_for_pending_client_request() -> None:
    session = _create_session()
    try:
        coach = _create_user(
            session,
            email="pending.routine.coach@example.com",
            full_name="Pending Routine Coach",
            role=UserRole.COACH,
        )
        client = _create_user(
            session,
            email="pending.routine.client@example.com",
            full_name="Pending Routine Client",
            role=UserRole.SELF,
        )
        session.add(
            CoachClient(
                coach_id=coach.id,
                client_id=client.id,
                status=CoachClientStatus.PENDING,
                assign_initial_plan=False,
            )
        )
        session.commit()

        service = RoutineService(RoutineRepository(session))
        with pytest.raises(RoutineClientNotManagedError):
            service.get_or_create_client_routine_for_date(
                current_coach=coach,
                client_id=client.id,
                target_date=date(2026, 7, 13),
            )
    finally:
        session.close()


def test_routine_macro_patch_updates_meals_kcal_and_remaining_goal() -> None:
    session = _create_session()
    try:
        user = _create_user(session)
        service = RoutineService(RoutineRepository(session))

        routine = service.create_routine(
            current_user=user,
            payload=RoutineCreate(
                date=date(2026, 7, 11),
                completion_status=False,
            ),
        )

        updated = service.patch_routine(
            current_user=user,
            routine_id=routine.id,
            payload=RoutinePatch(
                intake_protein=145,
                intake_carbs=210,
                intake_fats=70,
                intake_fiber=30,
                meals="Eggs, rice, fish",
                meals_kcal=2290,
                notes="Exceeded some macro targets",
            ),
        )

        read_model = RoutineRead.model_validate(updated)

        assert read_model.consumed_kcal == 2290.0
        assert read_model.remaining_kcal is None
        assert read_model.remaining_protein is None
        assert read_model.remaining_carbs is None
        assert read_model.remaining_fats is None
        assert read_model.remaining_fiber is None
        assert read_model.meals == "Eggs, rice, fish"
        assert read_model.notes == "Exceeded some macro targets"
    finally:
        session.close()


def test_routine_macro_log_flow_updates_totals_and_recent_foods() -> None:
    session = _create_session()
    try:
        user = _create_user(session)
        service = RoutineService(RoutineRepository(session))

        routine = service.get_or_create_routine_for_date(
            current_user=user,
            target_date=date(2026, 7, 12),
        )
        same_routine = service.get_or_create_routine_for_date(
            current_user=user,
            target_date=date(2026, 7, 12),
        )

        assert same_routine.id == routine.id

        updated_routine, first_log = service.add_macro_log(
            current_user=user,
            routine_id=routine.id,
            payload=RoutineMacroLogCreate(
                macro_type=MacroType.PROTEIN,
                meal_type=MealType.BREAKFAST,
                food_name="Chicken Breast",
                amount=100,
                amount_unit="grams",
                macro_grams=31,
                kcal=165,
                logged_at=datetime(2026, 7, 12, 8, 0, tzinfo=timezone.utc),
            ),
        )

        assert first_log.food_name == "Chicken Breast"
        assert first_log.meal_type == MealType.BREAKFAST
        assert updated_routine.intake_protein == 31.0
        assert updated_routine.meals_kcal == 165.0

        service.add_macro_log(
            current_user=user,
            routine_id=routine.id,
            payload=RoutineMacroLogCreate(
                macro_type=MacroType.PROTEIN,
                meal_type=MealType.BREAKFAST,
                food_name="Greek Yogurt",
                amount=170,
                amount_unit="grams",
                macro_grams=20,
                kcal=120,
                logged_at=datetime(2026, 7, 12, 9, 0, tzinfo=timezone.utc),
            ),
        )
        final_routine, latest_chicken_log = service.add_macro_log(
            current_user=user,
            routine_id=routine.id,
            payload=RoutineMacroLogCreate(
                macro_type=MacroType.PROTEIN,
                meal_type=MealType.LUNCH,
                food_name="Chicken Breast",
                amount=125,
                amount_unit="grams",
                macro_grams=39,
                kcal=206,
                logged_at=datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc),
            ),
        )

        logs = service.list_macro_logs(current_user=user, routine_id=routine.id)
        recent_foods = service.list_recent_macro_foods(
            current_user=user,
            macro_type=MacroType.PROTEIN,
            limit=2,
        )

        assert final_routine.intake_protein == 90.0
        assert final_routine.meals_kcal == 491.0
        assert [log.food_name for log in logs] == ["Chicken Breast", "Greek Yogurt", "Chicken Breast"]
        assert logs[0].id == latest_chicken_log.id
        assert logs[2].id == first_log.id
        assert [food.food_name for food in recent_foods] == ["Chicken Breast", "Greek Yogurt"]
        assert recent_foods[0].macro_grams == 39.0
        assert recent_foods[0].kcal == 206.0
    finally:
        session.close()
