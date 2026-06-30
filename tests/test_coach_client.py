from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_coach, get_current_user
from app.dependencies.coach_client import get_coach_client_service
from app.main import app
from app.models.coach_client import CoachClient
from app.models.user import User, UserRole
from app.services.coach_client_service import (
    CoachClientRelationshipExistsError,
    CoachClientRelationshipNotFoundError,
)


class FakeCoachClientService:
    def __init__(self, *, coach_user: User, clients: list[User]) -> None:
        self.coach_user = coach_user
        self.clients = {client.id: client for client in clients}
        now = datetime.now(tz=timezone.utc)
        self.relationships: dict = {
            clients[0].id: CoachClient(
                id=uuid4(),
                coach_id=coach_user.id,
                client_id=clients[0].id,
                created_at=now,
            )
        }

    def add_client(self, *, current_coach: User, client_id):
        if client_id in self.relationships:
            raise CoachClientRelationshipExistsError("Client already assigned to coach")

        relation = CoachClient(
            id=uuid4(),
            coach_id=current_coach.id,
            client_id=client_id,
            created_at=datetime.now(tz=timezone.utc),
        )
        self.relationships[client_id] = relation
        return relation

    def remove_client(self, *, current_coach: User, client_id):
        if client_id not in self.relationships:
            raise CoachClientRelationshipNotFoundError("Coach-client relationship not found")
        del self.relationships[client_id]

    def list_clients(self, *, current_coach: User):
        return [self.clients[client_id] for client_id in self.relationships if client_id in self.clients]

    def get_client_profile(self, *, current_coach: User, client_id):
        if client_id not in self.relationships or client_id not in self.clients:
            raise CoachClientRelationshipNotFoundError("Coach-client relationship not found")
        return self.clients[client_id]


def _build_user(*, role: UserRole, email: str, full_name: str) -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        email=email,
        hashed_password="hashed-password",
        full_name=full_name,
        age=29,
        gender="male",
        occupation="Athlete",
        fitness_goal="Improve strength",
        profile_image=None,
        reference_image=None,
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def coach_user() -> User:
    return _build_user(role=UserRole.COACH, email="coach@example.com", full_name="Coach User")


@pytest.fixture
def regular_user() -> User:
    return _build_user(role=UserRole.SELF, email="self@example.com", full_name="Self User")


@pytest.fixture
def clients() -> list[User]:
    return [
        _build_user(role=UserRole.SELF, email="client1@example.com", full_name="Client One"),
        _build_user(role=UserRole.SELF, email="client2@example.com", full_name="Client Two"),
    ]


@pytest.fixture
def fake_coach_client_service(coach_user: User, clients: list[User]) -> FakeCoachClientService:
    return FakeCoachClientService(coach_user=coach_user, clients=clients)


@pytest.fixture
def override_coach_service(fake_coach_client_service: FakeCoachClientService):
    app.dependency_overrides[get_coach_client_service] = lambda: fake_coach_client_service
    yield
    app.dependency_overrides.pop(get_coach_client_service, None)


@pytest.fixture
def override_current_coach(coach_user: User):
    app.dependency_overrides[get_current_coach] = lambda: coach_user
    yield
    app.dependency_overrides.pop(get_current_coach, None)


@pytest.mark.asyncio
async def test_list_clients(override_coach_service, override_current_coach) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/coach/clients")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["email"] == "client1@example.com"


@pytest.mark.asyncio
async def test_get_client_profile(override_coach_service, override_current_coach, clients: list[User]) -> None:
    target_client = clients[0]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"/coach/clients/{target_client.id}/profile")

    assert response.status_code == 200
    assert response.json()["email"] == target_client.email


@pytest.mark.asyncio
async def test_add_client_prevents_duplicates(
    override_coach_service,
    override_current_coach,
    clients: list[User],
) -> None:
    duplicate_client = clients[0]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/coach/clients", json={"client_id": str(duplicate_client.id)})

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_remove_client(override_coach_service, override_current_coach, clients: list[User]) -> None:
    target_client = clients[0]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.delete(f"/coach/clients/{target_client.id}")

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_coach_role_required(
    override_coach_service,
    regular_user: User,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: regular_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/coach/clients")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403