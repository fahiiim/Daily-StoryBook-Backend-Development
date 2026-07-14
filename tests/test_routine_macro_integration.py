from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.db.database import Base
from app.models.routine_macro_log import MacroType
from app.models.user import User, UserRole
from app.repositories.routine_repository import RoutineRepository
from app.schemas.routine import RoutineCreate, RoutineMacroLogCreate, RoutinePatch, RoutineRead
from app.services.routine_service import RoutineService


def _create_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def _create_user(session: Session) -> User:
    user = User(
        email="macro.integration@example.com",
        hashed_password=hash_password("secret123"),
        full_name="Macro Integration User",
        date_of_birth=date(1998, 1, 1),
        role=UserRole.SELF,
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
                goal_kcal=2200,
                goal_protein=150,
                goal_carbs=250,
                goal_fats=70,
                goal_fiber=30,
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
        assert read_model.remaining_kcal == 620.0
        assert read_model.remaining_protein == 50.0
        assert read_model.remaining_carbs == 130.0
        assert read_model.remaining_fats == 30.0
        assert read_model.remaining_fiber == 10.0
        assert read_model.meals == "Oats and chicken"
        assert read_model.notes == "All meals tracked"
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
                goal_kcal=2000,
                goal_protein=140,
                goal_carbs=230,
                goal_fats=65,
                goal_fiber=28,
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
        assert read_model.remaining_kcal == -290.0
        assert read_model.remaining_protein == -5.0
        assert read_model.remaining_carbs == 20.0
        assert read_model.remaining_fats == -5.0
        assert read_model.remaining_fiber == -2.0
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
                food_name="Chicken Breast",
                amount=100,
                amount_unit="grams",
                macro_grams=31,
                kcal=165,
                logged_at=datetime(2026, 7, 12, 8, 0, tzinfo=timezone.utc),
            ),
        )

        assert first_log.food_name == "Chicken Breast"
        assert updated_routine.intake_protein == 31.0
        assert updated_routine.meals_kcal == 165.0

        service.add_macro_log(
            current_user=user,
            routine_id=routine.id,
            payload=RoutineMacroLogCreate(
                macro_type=MacroType.PROTEIN,
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
