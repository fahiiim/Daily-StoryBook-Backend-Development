from datetime import date
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_user
from app.dependencies.profile import get_profile_service
from app.main import app
from app.models.user import User, UserRole
from app.schemas.profile import (
    ClientManagementLimitsRead,
    CoachSettingsRead,
    CoachSettingsUpdateRequest,
    PasswordUpdateRequest,
    ProfilePatchRequest,
    ProfilePutRequest,
    SelfProfileRead,
    SelfProfileUpdateRequest,
)
from app.services.profile_service import (
    EmptyProfileUpdateError,
    InvalidCurrentPasswordError,
    ProfileRoleRequiredError,
)


class FakeProfileService:
    def __init__(self, user: User) -> None:
        self.user = user
        self.deleted = False

    def get_profile(self, _: User) -> User:
        return self.user

    def replace_profile(self, _: User, payload: ProfilePutRequest) -> User:
        self.user.full_name = payload.name
        self.user.date_of_birth = payload.date_of_birth
        self.user.occupation = payload.occupation
        self.user.fitness_goal = payload.fitness_goal
        self.user.bio = payload.bio
        self.user.profile_image = payload.profile_image
        self.user.reference_image = payload.reference_image
        self.user.use_reference_image = payload.use_reference_image
        self.user.updated_at = datetime.now(tz=timezone.utc)
        return self.user

    def get_self_profile(self, current_user: User) -> SelfProfileRead:
        _ = current_user
        if self.user.role != UserRole.SELF:
            raise ProfileRoleRequiredError("SELF role required")
        return SelfProfileRead(
            id=self.user.id,
            username=self.user.username,
            email=self.user.email,
            name=self.user.full_name,
            role=UserRole.SELF,
            date_of_birth=self.user.date_of_birth,
            bio=self.user.bio,
            profile_image=self.user.profile_image,
            reference_image=self.user.reference_image,
            use_reference_image=self.user.use_reference_image,
            subscription_plan=None,
            is_email_verified=self.user.is_email_verified,
            created_at=self.user.created_at,
            updated_at=self.user.updated_at,
        )

    def update_self_profile(self, current_user: User, payload: SelfProfileUpdateRequest) -> SelfProfileRead:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise EmptyProfileUpdateError("No profile fields were provided")

        if "name" in updates:
            self.user.full_name = str(updates["name"])
        if "date_of_birth" in updates:
            self.user.date_of_birth = updates["date_of_birth"]
        if "bio" in updates:
            self.user.bio = updates["bio"]
        if "profile_image" in updates:
            self.user.profile_image = updates["profile_image"]
        if "reference_image" in updates:
            self.user.reference_image = updates["reference_image"]
        if "use_reference_image" in updates:
            self.user.use_reference_image = bool(updates["use_reference_image"])

        self.user.updated_at = datetime.now(tz=timezone.utc)
        return self.get_self_profile(current_user)

    def get_coach_settings(self, current_user: User) -> CoachSettingsRead:
        _ = current_user
        if self.user.role != UserRole.COACH:
            raise ProfileRoleRequiredError("COACH role required")
        return CoachSettingsRead(
            id=self.user.id,
            email=self.user.email,
            name=self.user.full_name,
            role=UserRole.COACH,
            phone_number=self.user.phone_number,
            bio=self.user.bio,
            updated_at=self.user.updated_at,
        )

    def update_coach_settings(self, current_user: User, payload: CoachSettingsUpdateRequest) -> CoachSettingsRead:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise EmptyProfileUpdateError("No coach settings fields were provided")
        if "name" in updates:
            self.user.full_name = str(updates["name"])
        if "phone_number" in updates:
            self.user.phone_number = updates["phone_number"]
        if "bio" in updates:
            self.user.bio = updates["bio"]
        self.user.updated_at = datetime.now(tz=timezone.utc)
        return self.get_coach_settings(current_user)

    def update_coach_password(self, current_user: User, payload: PasswordUpdateRequest) -> None:
        _ = current_user
        if self.user.role != UserRole.COACH:
            raise ProfileRoleRequiredError("COACH role required")
        if payload.current_password != "oldsecret123":
            raise InvalidCurrentPasswordError("Current password is incorrect")

    def delete_account(self, current_user: User) -> None:
        _ = current_user
        self.deleted = True

    def get_coach_client_management_limits(self, current_user: User) -> ClientManagementLimitsRead:
        _ = current_user
        if self.user.role != UserRole.COACH:
            raise ProfileRoleRequiredError("COACH role required")
        return ClientManagementLimitsRead(max_client_capacity=25, current_clients=7)

    def patch_profile(self, _: User, payload: ProfilePatchRequest) -> User:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise EmptyProfileUpdateError("No profile fields were provided")

        if "name" in updates:
            self.user.full_name = str(updates["name"])
        if "date_of_birth" in updates:
            self.user.date_of_birth = updates["date_of_birth"]
        if "occupation" in updates:
            self.user.occupation = updates["occupation"]
        if "fitness_goal" in updates:
            self.user.fitness_goal = updates["fitness_goal"]
        if "bio" in updates:
            self.user.bio = updates["bio"]
        if "profile_image" in updates:
            self.user.profile_image = updates["profile_image"]
        if "reference_image" in updates:
            self.user.reference_image = updates["reference_image"]
        if "use_reference_image" in updates:
            self.user.use_reference_image = bool(updates["use_reference_image"])

        self.user.updated_at = datetime.now(tz=timezone.utc)
        return self.user


@pytest.fixture
def profile_user() -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        username="profile_user",
        email="profile.user@example.com",
        hashed_password="hashed-password",
        full_name="Profile User",
        age=None,
        date_of_birth=date(1994, 3, 15),
        gender="female",
        occupation="Engineer",
        fitness_goal="Build strength",
        bio=None,
        profile_image="https://example.com/profile.jpg",
        reference_image="https://example.com/reference.jpg",
        use_reference_image=False,
        role=UserRole.SELF,
        is_email_verified=False,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def coach_user() -> User:
    now = datetime.now(tz=timezone.utc)
    return User(
        id=uuid4(),
        username="coach_profile_user",
        email="coach.profile@example.com",
        hashed_password="hashed-password",
        full_name="Coach Profile",
        age=None,
        date_of_birth=None,
        gender=None,
        occupation=None,
        fitness_goal=None,
        bio="Coach biography",
        profile_image=None,
        reference_image=None,
        use_reference_image=False,
        role=UserRole.COACH,
        phone_number="+15550001111",
        max_client_capacity=25,
        is_email_verified=True,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def fake_profile_service(profile_user: User) -> FakeProfileService:
    return FakeProfileService(profile_user)


@pytest.fixture
def fake_coach_profile_service(coach_user: User) -> FakeProfileService:
    return FakeProfileService(coach_user)


@pytest.fixture
def override_profile_service(fake_profile_service: FakeProfileService):
    app.dependency_overrides[get_profile_service] = lambda: fake_profile_service
    yield
    app.dependency_overrides.pop(get_profile_service, None)


@pytest.fixture
def override_current_user(profile_user: User):
    app.dependency_overrides[get_current_user] = lambda: profile_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def override_coach_dependencies(
    coach_user: User,
    fake_coach_profile_service: FakeProfileService,
):
    app.dependency_overrides[get_current_user] = lambda: coach_user
    app.dependency_overrides[get_profile_service] = lambda: fake_coach_profile_service
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_profile_service, None)


@pytest.mark.asyncio
async def test_get_profile_authenticated(
    override_profile_service,
    override_current_user,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/profile")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "profile.user@example.com"
    assert data["name"] == "Profile User"


@pytest.mark.asyncio
async def test_get_self_profile_section(override_profile_service, override_current_user) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/profile/self")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Profile User"
    assert data["age"] is not None
    assert data["profile_image"] == "https://example.com/profile.jpg"
    assert data["reference_image"] == "https://example.com/reference.jpg"
    assert data["subscription_plan"] is None


@pytest.mark.asyncio
async def test_patch_self_profile_settings(override_profile_service, override_current_user) -> None:
    payload = {
        "name": "Updated Self",
        "bio": "Self biography",
        "profile_image": "https://example.com/self.jpg",
        "reference_image": "https://example.com/ref.jpg",
        "use_reference_image": True,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.patch("/profile/self/settings", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Self"
    assert data["bio"] == "Self biography"
    assert data["use_reference_image"] is True


@pytest.mark.asyncio
async def test_logout_profile(override_profile_service, override_current_user) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/profile/logout")

    assert response.status_code == 200
    assert response.json()["message"].startswith("Logout successful")


@pytest.mark.asyncio
async def test_delete_account(override_profile_service, override_current_user, fake_profile_service: FakeProfileService) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.delete("/profile/account")

    assert response.status_code == 204
    assert fake_profile_service.deleted is True


@pytest.mark.asyncio
async def test_get_coach_settings(override_coach_dependencies) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/profile/coach/settings")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Coach Profile"
    assert data["phone_number"] == "+15550001111"
    assert data["bio"] == "Coach biography"


@pytest.mark.asyncio
async def test_patch_coach_settings(override_coach_dependencies) -> None:
    payload = {
        "name": "Updated Coach",
        "phone_number": "+15552223333",
        "bio": "Updated coach bio",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.patch("/profile/coach/settings", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Coach"
    assert data["phone_number"] == "+15552223333"
    assert data["bio"] == "Updated coach bio"


@pytest.mark.asyncio
async def test_patch_coach_password(override_coach_dependencies) -> None:
    payload = {
        "current_password": "oldsecret123",
        "new_password": "newsecret123",
        "confirm_password": "newsecret123",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.patch("/profile/coach/password", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Password updated successfully"


@pytest.mark.asyncio
async def test_patch_coach_password_rejects_wrong_current_password(override_coach_dependencies) -> None:
    payload = {
        "current_password": "wrongsecret",
        "new_password": "newsecret123",
        "confirm_password": "newsecret123",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.patch("/profile/coach/password", json=payload)

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_coach_client_management_limits(override_coach_dependencies) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/profile/coach/client-management-limits")

    assert response.status_code == 200
    data = response.json()
    assert data["max_client_capacity"] == 25
    assert data["current_clients"] == 7
    assert data["remaining_client_capacity"] == 18


@pytest.mark.asyncio
async def test_put_profile_authenticated(
    override_profile_service,
    override_current_user,
) -> None:
    payload = {
        "name": "Updated Name",
        "date_of_birth": "1993-04-10",
        "occupation": "Product Designer",
        "fitness_goal": "Improve mobility",
        "bio": "Fitness enthusiast",
        "profile_image": "https://example.com/new-profile.jpg",
        "reference_image": "https://example.com/new-reference.jpg",
        "use_reference_image": True,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.put("/profile", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["occupation"] == "Product Designer"


@pytest.mark.asyncio
async def test_patch_profile_authenticated(
    override_profile_service,
    override_current_user,
) -> None:
    payload = {
        "occupation": "Athlete",
        "fitness_goal": "Run a marathon",
        "use_reference_image": True,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.patch("/profile", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["occupation"] == "Athlete"
    assert data["fitness_goal"] == "Run a marathon"


@pytest.mark.asyncio
async def test_profile_requires_authentication(override_profile_service) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/profile")

    assert response.status_code == 401