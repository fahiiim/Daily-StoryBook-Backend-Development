from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.admin.dashboard_data import AdminDashboardData, AdminDashboardNotFoundError
from app.db.database import Base
from app.models.coach_client import CoachClient, CoachClientStatus
from app.models.user import User, UserRole


@pytest.fixture
def sqlite_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _create_user(
    session: Session,
    *,
    email: str,
    name: str,
    role: UserRole,
    active: bool = True,
    capacity: int = 20,
    occupation: str | None = None,
) -> User:
    user = User(
        email=email,
        hashed_password="hashed-password",
        full_name=name,
        role=role,
        is_active=active,
        is_email_verified=True,
        max_client_capacity=capacity,
        occupation=occupation,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_list_coaches_reports_assignment_counts_and_capacity(
    sqlite_session: Session,
) -> None:
    coach = _create_user(
        sqlite_session,
        email="coach@example.com",
        name="Coach Carter",
        role=UserRole.COACH,
        capacity=2,
        occupation="Strength coach",
    )
    inactive_coach = _create_user(
        sqlite_session,
        email="inactive@example.com",
        name="Inactive Coach",
        role=UserRole.COACH,
        active=False,
    )
    accepted_client = _create_user(
        sqlite_session,
        email="accepted@example.com",
        name="Accepted Client",
        role=UserRole.SELF,
    )
    pending_client = _create_user(
        sqlite_session,
        email="pending@example.com",
        name="Pending Client",
        role=UserRole.SELF,
    )
    sqlite_session.add_all(
        [
            CoachClient(
                coach_id=coach.id,
                client_id=accepted_client.id,
                status=CoachClientStatus.ACCEPTED,
            ),
            CoachClient(
                coach_id=coach.id,
                client_id=pending_client.id,
                status=CoachClientStatus.PENDING,
            ),
        ]
    )
    sqlite_session.commit()

    rows = AdminDashboardData(sqlite_session).list_coaches(
        search=None,
        status_filter=None,
    )
    by_id = {row["id"]: row for row in rows}

    assert by_id[coach.id]["active_clients"] == 1
    assert by_id[coach.id]["pending_requests"] == 1
    assert by_id[coach.id]["available_slots"] == 1
    assert by_id[coach.id]["utilization"] == 50
    assert by_id[coach.id]["status"] == "Available"
    assert by_id[coach.id]["specialty"] == "Strength coach"
    assert by_id[inactive_coach.id]["status"] == "Inactive"

    filtered = AdminDashboardData(sqlite_session).list_coaches(
        search="strength",
        status_filter="available",
    )
    assert [row["id"] for row in filtered] == [coach.id]


def test_get_coach_includes_client_relationship_details(
    sqlite_session: Session,
) -> None:
    coach = _create_user(
        sqlite_session,
        email="coach@example.com",
        name="Coach Carter",
        role=UserRole.COACH,
        capacity=1,
        occupation="Strength coach",
    )
    client = _create_user(
        sqlite_session,
        email="client@example.com",
        name="Client One",
        role=UserRole.SELF,
    )
    client.fitness_goal = "Build strength"
    relationship = CoachClient(
        coach_id=coach.id,
        client_id=client.id,
        status=CoachClientStatus.ACCEPTED,
        assign_initial_plan=True,
        personalized_message="Welcome to the program.",
    )
    sqlite_session.add_all([client, relationship])
    sqlite_session.commit()

    result = AdminDashboardData(sqlite_session).get_coach(coach_id=coach.id)

    assert result["active_clients"] == 1
    assert result["available_slots"] == 0
    assert result["status"] == "Full"
    assert result["account_status"] == "Active"
    assignments = result["assignments"]
    assert isinstance(assignments, list)
    assert len(assignments) == 1
    assert assignments[0]["id"] == client.id
    assert assignments[0]["goal"] == "Build Strength"
    assert assignments[0]["relationship_status"] == "Accepted"
    assert assignments[0]["initial_plan"] is True
    assert assignments[0]["message"] == "Welcome to the program."


def test_get_coach_rejects_non_coach_user(sqlite_session: Session) -> None:
    client = _create_user(
        sqlite_session,
        email="client@example.com",
        name="Client One",
        role=UserRole.SELF,
    )

    with pytest.raises(AdminDashboardNotFoundError, match="Coach not found"):
        AdminDashboardData(sqlite_session).get_coach(coach_id=client.id)

    with pytest.raises(AdminDashboardNotFoundError, match="Coach not found"):
        AdminDashboardData(sqlite_session).get_coach(coach_id=uuid4())


def test_export_coaches_contains_capacity_information(sqlite_session: Session) -> None:
    coach = _create_user(
        sqlite_session,
        email="coach@example.com",
        name="Coach Carter",
        role=UserRole.COACH,
        capacity=12,
        occupation="Strength coach",
    )

    rows = AdminDashboardData(sqlite_session).export_coaches()

    assert rows == [
        [
            str(coach.id),
            "Coach Carter",
            "coach@example.com",
            "Strength coach",
            "0",
            "12",
            "12",
            "Available",
            rows[0][8],
        ]
    ]
