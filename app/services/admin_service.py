from pathlib import Path
from uuid import UUID

from app.core.config import BASE_DIR, settings
from app.models.user import User, UserRole
from app.repositories.admin_repository import AdminRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin import (
    AdminDashboardResponse,
    AdminStorybookListResponse,
    AdminSubscriptionListResponse,
    AdminUserListResponse,
)
from app.schemas.storybook import StorybookRead
from app.schemas.subscription import SubscriptionRead
from app.schemas.user import UserRead


class AdminServiceError(Exception):
    pass


class AdminNotFoundError(AdminServiceError):
    pass


class AdminAccessError(AdminServiceError):
    pass


class AdminService:
    def __init__(self, *, admin_repository: AdminRepository, user_repository: UserRepository) -> None:
        self.admin_repository = admin_repository
        self.user_repository = user_repository

    def get_dashboard(self, *, current_admin: User) -> AdminDashboardResponse:
        self._ensure_admin(current_admin)
        return AdminDashboardResponse(
            total_users=self.admin_repository.count_users(),
            active_users=self.admin_repository.count_active_users(),
            total_coaches=self.admin_repository.count_coaches(),
            stories_generated=self.admin_repository.count_storybooks(),
            subscriptions=self.admin_repository.count_subscriptions(),
            storage_usage_bytes=self._get_storage_usage_bytes(),
        )

    def list_users(
        self,
        *,
        current_admin: User,
        limit: int,
        offset: int,
        sort: str,
        sort_field: str,
        search: str | None,
        role: UserRole | None,
        is_active: bool | None,
    ) -> AdminUserListResponse:
        self._ensure_admin(current_admin)
        sort_desc = sort.lower() != "asc"
        items, total = self.admin_repository.list_users(
            limit=limit,
            offset=offset,
            sort_desc=sort_desc,
            sort_field=sort_field,
            search=search,
            role=role,
            is_active=is_active,
        )
        return AdminUserListResponse(
            items=[UserRead.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    def list_storybooks(
        self,
        *,
        current_admin: User,
        limit: int,
        offset: int,
        sort: str,
        user_id: UUID | None,
        status: str | None,
        start_date,
        end_date,
    ) -> AdminStorybookListResponse:
        self._ensure_admin(current_admin)
        sort_desc = sort.lower() != "asc"
        items, total = self.admin_repository.list_storybooks(
            limit=limit,
            offset=offset,
            sort_desc=sort_desc,
            user_id=user_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )
        return AdminStorybookListResponse(
            items=[StorybookRead.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    def list_subscriptions(
        self,
        *,
        current_admin: User,
        limit: int,
        offset: int,
        sort: str,
        user_id: UUID | None,
        status: str | None,
    ) -> AdminSubscriptionListResponse:
        self._ensure_admin(current_admin)
        sort_desc = sort.lower() != "asc"
        items, total = self.admin_repository.list_subscriptions(
            limit=limit,
            offset=offset,
            sort_desc=sort_desc,
            user_id=user_id,
            status=status,
        )
        return AdminSubscriptionListResponse(
            items=[SubscriptionRead.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    def block_user(self, *, current_admin: User, user_id: UUID) -> UserRead:
        self._ensure_admin(current_admin)
        user = self._get_user_or_error(user_id=user_id)
        updated = self.user_repository.update_fields(user=user, updates={"is_active": False})
        return UserRead.model_validate(updated)

    def activate_user(self, *, current_admin: User, user_id: UUID) -> UserRead:
        self._ensure_admin(current_admin)
        user = self._get_user_or_error(user_id=user_id)
        updated = self.user_repository.update_fields(user=user, updates={"is_active": True})
        return UserRead.model_validate(updated)

    def soft_delete_user(self, *, current_admin: User, user_id: UUID) -> None:
        self._ensure_admin(current_admin)
        user = self._get_user_or_error(user_id=user_id)
        self.user_repository.update_fields(user=user, updates={"is_active": False})

    def _get_user_or_error(self, *, user_id: UUID) -> User:
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise AdminNotFoundError("User not found")
        return user

    @staticmethod
    def _ensure_admin(current_user: User) -> None:
        if current_user.role != UserRole.ADMIN:
            raise AdminAccessError("Admin role required")

    @staticmethod
    def _get_storage_usage_bytes() -> int:
        if settings.storage_backend.strip().lower() != "local":
            return 0

        media_root = BASE_DIR / settings.local_storage_dir
        if not media_root.exists():
            return 0

        total = 0
        for path in media_root.rglob("*"):
            if path.is_file():
                try:
                    total += path.stat().st_size
                except OSError:
                    continue
        return total
