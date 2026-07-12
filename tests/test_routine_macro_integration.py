from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.db.database import Base
from app.models.user import User, UserRole
from app.repositories.routine_repository import RoutineRepository
from app.schemas.routine import RoutineCreate, RoutinePatch, RoutineRead
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
        username="macro_integration_user",
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
                meals_kcal=300,
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
                meals_kcal=180,
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
