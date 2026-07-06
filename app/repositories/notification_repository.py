from uuid import UUID
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_user(
        self,
        *,
        user_id: UUID,
        limit: int,
        offset: int,
        sort_desc: bool,
    ) -> tuple[list[Notification], int]:
        order_by = Notification.created_at.desc() if sort_desc else Notification.created_at.asc()
        statement = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(order_by)
            .limit(limit)
            .offset(offset)
        )
        items = list(self.db.scalars(statement))

        count_statement = select(func.count(Notification.id)).where(Notification.user_id == user_id)
        total = int(self.db.scalar(count_statement) or 0)
        return items, total

    def get_by_id_for_user(self, *, notification_id: UUID, user_id: UUID) -> Notification | None:
        statement = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        return self.db.scalar(statement)

    def mark_read(self, *, notification: Notification) -> Notification:
        notification.is_read = True
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_all_read(self, *, user_id: UUID) -> int:
        statement = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        result = self.db.execute(statement)
        self.db.commit()
        return int(result.rowcount or 0)

    def delete_for_user(self, *, notification_id: UUID, user_id: UUID) -> bool:
        statement = delete(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        result = self.db.execute(statement)
        self.db.commit()
        return bool(result.rowcount and result.rowcount > 0)

    def unread_count(self, *, user_id: UUID) -> int:
        statement = select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        return int(self.db.scalar(statement) or 0)

    def create(self, *, notification: Notification) -> Notification:
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def update_fields(self, *, notification: Notification, updates: dict[str, Any]) -> Notification:
        for field_name, value in updates.items():
            setattr(notification, field_name, value)

        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification
