from uuid import UUID

from app.models.notification import Notification
from app.models.user import User, UserRole
from app.repositories.notification_repository import NotificationRepository


class NotificationServiceError(Exception):
    pass


class NotificationNotFoundError(NotificationServiceError):
    pass


class NotificationAccessError(NotificationServiceError):
    pass


class NotificationService:
    def __init__(self, notification_repository: NotificationRepository) -> None:
        self.notification_repository = notification_repository

    def list_notifications(
        self,
        *,
        current_user: User,
        limit: int,
        offset: int,
        sort_desc: bool,
    ) -> tuple[list[Notification], int]:
        self._ensure_user_access(current_user)
        return self.notification_repository.list_by_user(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            sort_desc=sort_desc,
        )

    def mark_read(self, *, current_user: User, notification_id: UUID) -> Notification:
        self._ensure_user_access(current_user)
        notification = self.notification_repository.get_by_id_for_user(
            notification_id=notification_id,
            user_id=current_user.id,
        )
        if notification is None:
            raise NotificationNotFoundError("Notification not found")
        if notification.is_read:
            return notification
        return self.notification_repository.mark_read(notification=notification)

    def mark_all_read(self, *, current_user: User) -> int:
        self._ensure_user_access(current_user)
        return self.notification_repository.mark_all_read(user_id=current_user.id)

    def delete_notification(self, *, current_user: User, notification_id: UUID) -> None:
        self._ensure_user_access(current_user)
        deleted = self.notification_repository.delete_for_user(
            notification_id=notification_id,
            user_id=current_user.id,
        )
        if not deleted:
            raise NotificationNotFoundError("Notification not found")

    def unread_count(self, *, current_user: User) -> int:
        self._ensure_user_access(current_user)
        return self.notification_repository.unread_count(user_id=current_user.id)

    @staticmethod
    def _ensure_user_access(current_user: User) -> None:
        if current_user.role not in {UserRole.SELF, UserRole.COACH, UserRole.ADMIN}:
            raise NotificationAccessError("Access to notifications is forbidden")
