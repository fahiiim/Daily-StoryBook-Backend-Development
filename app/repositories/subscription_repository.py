from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import Subscription, SubscriptionStatus


class SubscriptionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_current_for_user(self, *, user_id: UUID) -> Subscription | None:
        statement = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]),
            )
            .order_by(Subscription.created_at.desc())
        )
        return self.db.scalar(statement)