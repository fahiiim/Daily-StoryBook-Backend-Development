from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.user_repository import UserRepository
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
from app.schemas.subscription import SubscriptionRead


class ProfileServiceError(Exception):
    pass


class ProfileNotFoundError(ProfileServiceError):
    pass


class EmptyProfileUpdateError(ProfileServiceError):
    pass


class InvalidProfileDataError(ProfileServiceError):
    pass


class ProfileRoleRequiredError(ProfileServiceError):
    pass


class InvalidCurrentPasswordError(ProfileServiceError):
    pass


class ProfileService:
    def __init__(
        self,
        user_repository: UserRepository,
        subscription_repository: SubscriptionRepository | None = None,
        coach_client_repository: CoachClientRepository | None = None,
    ) -> None:
        self.user_repository = user_repository
        self.subscription_repository = subscription_repository or SubscriptionRepository(user_repository.db)
        self.coach_client_repository = coach_client_repository or CoachClientRepository(user_repository.db)

    def get_profile(self, current_user: User) -> User:
        user = self.user_repository.get_by_id(current_user.id)
        if user is None:
            raise ProfileNotFoundError("Profile not found")
        return user

    def replace_profile(self, current_user: User, payload: ProfilePutRequest) -> User:
        user = self.get_profile(current_user)
        updates = self._normalize_updates(payload.model_dump())
        return self.user_repository.update_fields(user=user, updates=updates)

    def patch_profile(self, current_user: User, payload: ProfilePatchRequest) -> User:
        user = self.get_profile(current_user)
        raw_updates = payload.model_dump(exclude_unset=True)
        if not raw_updates:
            raise EmptyProfileUpdateError("No profile fields were provided")

        updates = self._normalize_updates(raw_updates)
        return self.user_repository.update_fields(user=user, updates=updates)

    def get_self_profile(self, current_user: User) -> SelfProfileRead:
        user = self.get_profile(current_user)
        self._ensure_role(user=user, expected_role=UserRole.SELF)
        return self._build_self_profile(user)

    def update_self_profile(
        self,
        current_user: User,
        payload: SelfProfileUpdateRequest,
    ) -> SelfProfileRead:
        user = self.get_profile(current_user)
        self._ensure_role(user=user, expected_role=UserRole.SELF)

        raw_updates = payload.model_dump(exclude_unset=True)
        if not raw_updates:
            raise EmptyProfileUpdateError("No profile fields were provided")

        updates = self._normalize_updates(raw_updates)
        updated_user = self.user_repository.update_fields(user=user, updates=updates)
        return self._build_self_profile(updated_user)

    def get_coach_settings(self, current_user: User) -> CoachSettingsRead:
        user = self.get_profile(current_user)
        self._ensure_role(user=user, expected_role=UserRole.COACH)
        return self._build_coach_settings(user)

    def update_coach_settings(
        self,
        current_user: User,
        payload: CoachSettingsUpdateRequest,
    ) -> CoachSettingsRead:
        user = self.get_profile(current_user)
        self._ensure_role(user=user, expected_role=UserRole.COACH)

        raw_updates = payload.model_dump(exclude_unset=True)
        if not raw_updates:
            raise EmptyProfileUpdateError("No coach settings fields were provided")

        updates = self._normalize_updates(raw_updates)
        updated_user = self.user_repository.update_fields(user=user, updates=updates)
        return self._build_coach_settings(updated_user)

    def update_password(self, current_user: User, payload: PasswordUpdateRequest) -> None:
        user = self.get_profile(current_user)
        self._update_password_for_user(user=user, payload=payload)

    def update_coach_password(self, current_user: User, payload: PasswordUpdateRequest) -> None:
        user = self.get_profile(current_user)
        self._ensure_role(user=user, expected_role=UserRole.COACH)
        self._update_password_for_user(user=user, payload=payload)

    def _update_password_for_user(self, *, user: User, payload: PasswordUpdateRequest) -> None:
        if not verify_password(payload.current_password, user.hashed_password):
            raise InvalidCurrentPasswordError("Current password is incorrect")

        self.user_repository.update_fields(
            user=user,
            updates={"hashed_password": hash_password(payload.new_password)},
        )

    def delete_account(self, current_user: User) -> None:
        user = self.get_profile(current_user)
        self.user_repository.delete(user=user)

    def get_coach_client_management_limits(self, current_user: User) -> ClientManagementLimitsRead:
        user = self.get_profile(current_user)
        self._ensure_role(user=user, expected_role=UserRole.COACH)
        current_clients = self.coach_client_repository.count_clients(coach_id=user.id)
        return ClientManagementLimitsRead(
            max_client_capacity=user.max_client_capacity or 20,
            current_clients=current_clients,
        )

    def _normalize_updates(self, raw_updates: dict[str, object]) -> dict[str, object]:
        if "name" in raw_updates and raw_updates["name"] is None:
            raise InvalidProfileDataError("name cannot be null")

        updates: dict[str, object] = {}
        for field_name, value in raw_updates.items():
            if field_name == "name":
                updates["full_name"] = value.strip() if isinstance(value, str) else value
                continue
            updates[field_name] = value

        return updates

    def _ensure_role(self, *, user: User, expected_role: UserRole) -> None:
        if user.role != expected_role:
            raise ProfileRoleRequiredError(f"{expected_role.value} role required")

    def _build_self_profile(self, user: User) -> SelfProfileRead:
        subscription = self.subscription_repository.get_current_for_user(user_id=user.id)
        return SelfProfileRead(
            id=user.id,
            username=user.username,
            email=user.email,
            name=user.full_name,
            role=user.role or UserRole.SELF,
            date_of_birth=user.date_of_birth,
            bio=user.bio,
            profile_image=user.profile_image,
            reference_image=user.reference_image,
            use_reference_image=user.use_reference_image,
            subscription_plan=SubscriptionRead.model_validate(subscription) if subscription else None,
            is_email_verified=user.is_email_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def _build_coach_settings(self, user: User) -> CoachSettingsRead:
        return CoachSettingsRead(
            id=user.id,
            email=user.email,
            name=user.full_name,
            role=user.role or UserRole.COACH,
            phone_number=user.phone_number,
            bio=user.bio,
            updated_at=user.updated_at,
        )