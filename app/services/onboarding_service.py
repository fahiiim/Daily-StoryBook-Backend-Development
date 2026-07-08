from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.onboarding import OnboardingRoleRequest


class OnboardingServiceError(Exception):
    pass


class OnboardingUserNotFoundError(OnboardingServiceError):
    pass


class RoleAlreadySelectedError(OnboardingServiceError):
    pass


class OnboardingService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    def set_initial_role(self, *, current_user: User, payload: OnboardingRoleRequest) -> User:
        user = self.user_repository.get_by_id(current_user.id)
        if user is None:
            raise OnboardingUserNotFoundError("User not found")

        if user.role is not None:
            raise RoleAlreadySelectedError("Role has already been selected")

        selected_role = UserRole(payload.role)
        return self.user_repository.update_fields(user=user, updates={"role": selected_role})
