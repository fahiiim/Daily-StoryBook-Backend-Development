from datetime import date
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_coach, get_current_user
from app.dependencies.coach_client import get_coach_client_service
from app.main import app
from app.models.coach_client import CoachClient, CoachClientStatus
from app.models.user import User, UserRole
from app.services.coach_client_service import (
    CoachClientIncomingRequest,
    CoachClientNotFoundError,
    CoachClientRequestNotFoundError,
    CoachClientRelationshipExistsError,
    CoachClientRelationshipNotFoundError,
    CoachClientSentRequest,
    InvalidCoachClientAssignmentError,
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
                personalized_message="Welcome to coaching",
                assign_initial_plan=True,
                status=CoachClientStatus.ACCEPTED,
                created_at=now,
            )
        }

    def add_client(
        self,
        *,
        current_coach: User,
        client_email: str,
        personalized_message: str | None = None,
        assign_initial_plan: bool = False,
    ):
        client = next(
            (
                client
                for client in self.clients.values()
                if client.email == client_email.strip().lower()
            ),
            None,
        )
        if client is None:
            raise CoachClientNotFoundError("Client not found")

        client_id = client.id

        if client_id in self.relationships:
            raise CoachClientRelationshipExistsError("Client already assigned to coach")

        relation = CoachClient(
            id=uuid4(),
            coach_id=current_coach.id,
            client_id=client_id,
            personalized_message=personalized_message.strip() if personalized_message else None,
            assign_initial_plan=assign_initial_plan,
            status=CoachClientStatus.PENDING,
            created_at=datetime.now(tz=timezone.utc),
        )
        self.relationships[client_id] = relation
        return relation

    def list_client_requests(self, *, current_user: User):
        if current_user.role != UserRole.SELF:
            raise InvalidCoachClientAssignmentError("SELF role required")
        return [
            CoachClientIncomingRequest(
                relationship=relationship,
                coach=self.coach_user,
            )
            for relationship in self.relationships.values()
            if relationship.client_id == current_user.id and relationship.status == CoachClientStatus.PENDING
        ]

    def list_sent_client_requests(self, *, current_coach: User):
        return [
            CoachClientSentRequest(
                relationship=relationship,
                client=self.clients[relationship.client_id],
            )
            for relationship in self.relationships.values()
            if relationship.coach_id == current_coach.id and relationship.client_id in self.clients
        ]

    def accept_client_request(self, *, current_user: User, request_id):
        if current_user.role != UserRole.SELF:
            raise InvalidCoachClientAssignmentError("SELF role required")

        request = next(
            (
                relationship
                for relationship in self.relationships.values()
                if relationship.id == request_id
                and relationship.client_id == current_user.id
                and relationship.status == CoachClientStatus.PENDING
            ),
            None,
        )
        if request is None:
            raise CoachClientRequestNotFoundError("Client request not found")

        request.status = CoachClientStatus.ACCEPTED
        return request

    def cancel_client_request(self, *, current_user: User, request_id):
        if current_user.role != UserRole.SELF:
            raise InvalidCoachClientAssignmentError("SELF role required")

        request = next(
            (
                relationship
                for relationship in self.relationships.values()
                if relationship.id == request_id
                and relationship.client_id == current_user.id
                and relationship.status == CoachClientStatus.PENDING
            ),
            None,
        )
        if request is None:
            raise CoachClientRequestNotFoundError("Client request not found")

        request.status = CoachClientStatus.DECLINED
        return request

    def remove_client(self, *, current_coach: User, client_id):
        if client_id not in self.relationships:
            raise CoachClientRelationshipNotFoundError("Coach-client relationship not found")
        del self.relationships[client_id]

    def list_clients(self, *, current_coach: User):
        return [
            self.clients[client_id]
            for client_id, relationship in self.relationships.items()
            if client_id in self.clients and relationship.status == CoachClientStatus.ACCEPTED
        ]

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
        age=None,
        date_of_birth=date(1995, 5, 5),
        gender="male",
        occupation="Athlete",
        fitness_goal="Improve strength",
        bio=None,
        profile_image=None,
        reference_image=None,
        use_reference_image=False,
        role=role,
        is_email_verified=False,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def coach_user() -> User:
    coach = _build_user(role=UserRole.COACH, email="coach@example.com", full_name="Coach User")
    coach.profile_image = "https://example.com/coach.jpg"
    return coach


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
        response = await client.post("/coach/clients", json={"client_email": duplicate_client.email})

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
async def test_add_client_not_found(override_coach_service, override_current_coach) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/coach/clients", json={"client_email": "missing@example.com"})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_add_client_by_email(override_coach_service, override_current_coach, clients: list[User]) -> None:
    target_client = clients[1]
    payload = {
        "client_email": target_client.email,
        "personalized_message": "Welcome, excited to work with you.",
        "assign_initial_plan": True,
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/coach/clients", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["client_id"] == str(target_client.id)
    assert data["personalized_message"] == "Welcome, excited to work with you."
    assert data["assign_initial_plan"] is True
    assert data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_self_user_lists_and_accepts_client_request(
    override_coach_service,
    clients: list[User],
    fake_coach_client_service: FakeCoachClientService,
) -> None:
    target_client = clients[1]
    pending_request = fake_coach_client_service.add_client(
        current_coach=fake_coach_client_service.coach_user,
        client_email=target_client.email,
        personalized_message="Please join my coaching roster.",
        assign_initial_plan=True,
    )
    app.dependency_overrides[get_current_user] = lambda: target_client
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            list_response = await client.get("/coach/client-requests")
            accept_response = await client.post(f"/coach/client-requests/{pending_request.id}/accept")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == str(pending_request.id)
    assert list_response.json()[0]["status"] == "PENDING"
    assert list_response.json()[0]["coach_name"] == "Coach User"
    assert list_response.json()[0]["coach_profile_image"] == "https://example.com/coach.jpg"
    assert list_response.json()[0]["can_cancel"] is True
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "ACCEPTED"
    assert fake_coach_client_service.relationships[target_client.id].status == CoachClientStatus.ACCEPTED


@pytest.mark.asyncio
async def test_self_user_cancels_client_request(
    override_coach_service,
    clients: list[User],
    fake_coach_client_service: FakeCoachClientService,
) -> None:
    target_client = clients[1]
    pending_request = fake_coach_client_service.add_client(
        current_coach=fake_coach_client_service.coach_user,
        client_email=target_client.email,
        personalized_message="Please join my coaching roster.",
        assign_initial_plan=True,
    )
    app.dependency_overrides[get_current_user] = lambda: target_client
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(f"/coach/client-requests/{pending_request.id}/cancel")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json()["status"] == "DECLINED"
    assert fake_coach_client_service.relationships[target_client.id].status == CoachClientStatus.DECLINED


@pytest.mark.asyncio
async def test_coach_lists_sent_client_requests_with_statuses(
    override_coach_service,
    override_current_coach,
    clients: list[User],
    fake_coach_client_service: FakeCoachClientService,
) -> None:
    pending_client = clients[1]
    fake_coach_client_service.add_client(
        current_coach=fake_coach_client_service.coach_user,
        client_email=pending_client.email,
        personalized_message="Please join my coaching roster.",
        assign_initial_plan=True,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/coach/client-requests/sent")

    assert response.status_code == 200
    data = response.json()
    statuses_by_email = {item["client_email"]: item["status"] for item in data}
    assert statuses_by_email["client1@example.com"] == "ACCEPTED"
    assert statuses_by_email["client2@example.com"] == "PENDING"
    pending_payload = next(item for item in data if item["client_email"] == "client2@example.com")
    assert pending_payload["client_name"] == "Client Two"
    assert pending_payload["personalized_message"] == "Please join my coaching roster."
    assert pending_payload["assign_initial_plan"] is True


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