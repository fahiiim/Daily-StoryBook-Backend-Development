from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.profile import ProfilePatchRequest, ProfilePutRequest


class ProfileServiceError(Exception):
    pass


class ProfileNotFoundError(ProfileServiceError):
    pass


class EmptyProfileUpdateError(ProfileServiceError):
    pass


class InvalidProfileDataError(ProfileServiceError):
    pass


class ProfileService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

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