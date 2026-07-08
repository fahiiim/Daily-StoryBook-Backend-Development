from datetime import date
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies.auth import get_current_user
from app.dependencies.profile import get_profile_service
from app.main import app
from app.models.user import User, UserRole
from app.schemas.profile import ProfilePatchRequest, ProfilePutRequest
from app.services.profile_service import EmptyProfileUpdateError


class FakeProfileService:
    def __init__(self, user: User) -> None:
        self.user = user

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
def fake_profile_service(profile_user: User) -> FakeProfileService:
    return FakeProfileService(profile_user)


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