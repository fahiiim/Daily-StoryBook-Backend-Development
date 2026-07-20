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
from app.schemas.routine import (
    RoutineCreate,
    RoutineMacroLogCreate,
    RoutineMacroLogUpdate,
    RoutinePatch,
    RoutineRead,
)
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
                notes="All meals tracked",
                completion_status=False,
            ),
        )

        routine, _ = service.add_macro_log(
            current_user=user,
            routine_id=routine.id,
            payload=RoutineMacroLogCreate(
                meal_type=MealType.LUNCH,
                food_name="Oats and chicken",
                kcal=1580,
                protein=100,
                carbs=120,
                fat=40,
                fiber=20,
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
            CoachClient(
                coach_id=coach.id,
                client_id=user.id,
                status=CoachClientStatus.ACCEPTED,
                assign_initial_plan=False,
            )
        )
        session.add(
            NutritionPlan(
                coach_id=coach.id,
                client_id=user.id,
                daily_calories=2200,
                protein=150,
                carbs=250,
                fat=70,
                fiber=30,
                water_goal=3.0,
                workout_plan=["Do 30 pushups"],
                daily_goals=["Drink 3 litres of water"],
                date=date(2026, 7, 10),
            )
        )
        session.commit()

        service = RoutineService(RoutineRepository(session))
        routine = service.create_routine(
            current_user=user,
            payload=RoutineCreate(
                date=date(2026, 7, 10),
                water_intake=1.2,
                completion_status=False,
            ),
        )
        routine, _ = service.add_macro_log(
            current_user=user,
            routine_id=routine.id,
            payload=RoutineMacroLogCreate(
                meal_type=MealType.LUNCH,
                food_name="Chicken rice bowl",
                kcal=1580,
                protein=100,
                carbs=120,
                fat=40,
                fiber=20,
            ),
        )
        nutrition_plan = service.get_nutrition_plan_for_date(
            client_id=user.id,
            routine_date=date(2026, 7, 10),
        )
        assert nutrition_plan is not None
        routine.goal_kcal = float(nutrition_plan.daily_calories or 0)
        routine.goal_protein = nutrition_plan.protein
        routine.goal_carbs = nutrition_plan.carbs
        routine.goal_fats = nutrition_plan.fat
        routine.goal_fiber = nutrition_plan.fiber
        read_model = RoutineRead.model_validate(routine)

        assert read_model.goal_kcal == 2200.0
        assert read_model.goal_protein == 150.0
        assert read_model.goal_carbs == 250.0
        assert read_model.goal_fats == 70.0
        assert read_model.goal_fiber == 30.0
        assert read_model.remaining_kcal == 620.0
        assert read_model.remaining_protein == 50.0
        assert read_model.remaining_carbs == 130.0
        assert read_model.remaining_fats == 30.0
        assert read_model.remaining_fiber == 10.0
        assert nutrition_plan.water_goal == 3.0
    finally:
        session.close()


def test_coach_can_only_read_existing_routine_for_accepted_client() -> None:
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
        assert service.get_client_routine_for_date(
            current_coach=coach,
            client_id=client.id,
            target_date=date(2026, 7, 13),
        ) is None

        routine = service.get_or_create_routine_for_date(
            current_user=client,
            target_date=date(2026, 7, 13),
        )
        updated_routine, log = service.add_macro_log(
            current_user=client,
            routine_id=routine.id,
            payload=RoutineMacroLogCreate(
                meal_type=MealType.LUNCH,
                food_name="Mediterranean Bowl",
                kcal=420,
                protein=24,
                carbs=45,
                fat=14,
                fiber=8,
                logged_at=datetime(2026, 7, 13, 12, 45, tzinfo=timezone.utc),
            ),
        )
        coach_routine = service.get_client_routine_for_date(
            current_coach=coach,
            client_id=client.id,
            target_date=date(2026, 7, 13),
        )
        logs = service.list_client_macro_logs(
            current_coach=coach,
            client_id=client.id,
            routine_id=routine.id,
        )

        assert routine.user_id == client.id
        assert coach_routine is not None
        assert coach_routine.id == routine.id
        assert updated_routine.intake_protein == 24.0
        assert updated_routine.intake_carbs == 45.0
        assert updated_routine.intake_fats == 14.0
        assert updated_routine.intake_fiber == 8.0
        assert updated_routine.meals_kcal == 420.0
        assert log.meal_type == MealType.LUNCH
        assert log.amount == 1.0
        assert log.amount_unit == "serving"
        assert [item.food_name for item in logs] == ["Mediterranean Bowl"]
    finally:
        session.close()


def test_coach_cannot_view_routine_for_pending_client_request() -> None:
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
            service.get_client_routine_for_date(
                current_coach=coach,
                client_id=client.id,
                target_date=date(2026, 7, 13),
            )
    finally:
        session.close()


def test_routine_patch_cannot_override_log_derived_totals() -> None:
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
                meals="Eggs, rice, fish",
                notes="Exceeded some macro targets",
            ),
        )

        read_model = RoutineRead.model_validate(updated)

        assert read_model.consumed_kcal is None
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
                meal_type=MealType.BREAKFAST,
                food_name="Chicken Breast",
                amount=100,
                amount_unit="grams",
                kcal=165,
                protein=31,
                carbs=0,
                fat=3.6,
                fiber=0,
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
                meal_type=MealType.BREAKFAST,
                food_name="Greek Yogurt",
                amount=170,
                amount_unit="grams",
                kcal=120,
                protein=20,
                carbs=8,
                fat=0,
                fiber=0,
                logged_at=datetime(2026, 7, 12, 9, 0, tzinfo=timezone.utc),
            ),
        )
        final_routine, latest_chicken_log = service.add_macro_log(
            current_user=user,
            routine_id=routine.id,
            payload=RoutineMacroLogCreate(
                meal_type=MealType.LUNCH,
                food_name="Chicken Breast",
                amount=125,
                amount_unit="grams",
                kcal=206,
                protein=39,
                carbs=0,
                fat=4.5,
                fiber=0,
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
        assert final_routine.intake_carbs == 8.0
        assert final_routine.intake_fats == 8.1
        assert final_routine.intake_fiber == 0.0
        assert final_routine.meals_kcal == 491.0
        assert [log.food_name for log in logs] == ["Chicken Breast", "Greek Yogurt", "Chicken Breast"]
        assert logs[0].id == latest_chicken_log.id
        assert logs[2].id == first_log.id
        assert [food.food_name for food in recent_foods] == ["Chicken Breast", "Greek Yogurt"]
        assert recent_foods[0].protein == 39.0
        assert recent_foods[0].kcal == 206.0
    finally:
        session.close()


def test_update_and_delete_logged_meal_recalculate_all_totals() -> None:
    session = _create_session()
    try:
        user = _create_user(session, email="meal.mutation@example.com")
        service = RoutineService(RoutineRepository(session))
        routine = service.get_or_create_routine_for_date(
            current_user=user,
            target_date=date(2026, 7, 20),
        )
        routine, first_log = service.add_macro_log(
            current_user=user,
            routine_id=routine.id,
            payload=RoutineMacroLogCreate(
                meal_type=MealType.BREAKFAST,
                food_name="Eggs and toast",
                kcal=400,
                protein=25,
                carbs=35,
                fat=18,
                fiber=5,
            ),
        )
        routine, second_log = service.add_macro_log(
            current_user=user,
            routine_id=routine.id,
            payload=RoutineMacroLogCreate(
                meal_type=MealType.LUNCH,
                food_name="Chicken bowl",
                kcal=600,
                protein=45,
                carbs=70,
                fat=15,
                fiber=9,
            ),
        )

        routine, updated_log = service.update_macro_log(
            current_user=user,
            routine_id=routine.id,
            log_id=first_log.id,
            payload=RoutineMacroLogUpdate(
                kcal=450,
                protein=30,
                carbs=40,
                fat=20,
                fiber=6,
            ),
        )

        assert updated_log.kcal == 450.0
        assert routine.meals_kcal == 1050.0
        assert routine.intake_protein == 75.0
        assert routine.intake_carbs == 110.0
        assert routine.intake_fats == 35.0
        assert routine.intake_fiber == 15.0

        routine = service.delete_macro_log(
            current_user=user,
            routine_id=routine.id,
            log_id=second_log.id,
        )

        assert routine.meals_kcal == 450.0
        assert routine.intake_protein == 30.0
        assert routine.intake_carbs == 40.0
        assert routine.intake_fats == 20.0
        assert routine.intake_fiber == 6.0
    finally:
        session.close()
