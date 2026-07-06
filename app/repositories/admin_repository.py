from datetime import date
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.storybook import Storybook
from app.models.subscription import Subscription
from app.models.user import User, UserRole


class AdminRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def count_users(self) -> int:
        return int(self.db.scalar(select(func.count(User.id))) or 0)

    def count_active_users(self) -> int:
        statement = select(func.count(User.id)).where(User.is_active.is_(True))
        return int(self.db.scalar(statement) or 0)

    def count_coaches(self) -> int:
        statement = select(func.count(User.id)).where(User.role == UserRole.COACH)
        return int(self.db.scalar(statement) or 0)

    def count_storybooks(self) -> int:
        return int(self.db.scalar(select(func.count(Storybook.id))) or 0)

    def count_subscriptions(self) -> int:
        return int(self.db.scalar(select(func.count(Subscription.id))) or 0)

    def list_users(
        self,
        *,
        limit: int,
        offset: int,
        sort_desc: bool,
        sort_field: str,
        search: str | None,
        role: UserRole | None,
        is_active: bool | None,
    ) -> tuple[list[User], int]:
        statement = select(User)
        if search:
            search_term = f"%{search.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(User.email).like(search_term),
                    func.lower(User.full_name).like(search_term),
                )
            )

        if role is not None:
            statement = statement.where(User.role == role)

        if is_active is not None:
            statement = statement.where(User.is_active.is_(is_active))

        order_column = User.created_at
        if sort_field == "email":
            order_column = User.email
        elif sort_field == "full_name":
            order_column = User.full_name

        statement = statement.order_by(order_column.desc() if sort_desc else order_column.asc())
        items = list(self.db.scalars(statement.limit(limit).offset(offset)))

        count_statement = select(func.count(User.id))
        if search:
            count_statement = count_statement.where(
                or_(
                    func.lower(User.email).like(search_term),
                    func.lower(User.full_name).like(search_term),
                )
            )
        if role is not None:
            count_statement = count_statement.where(User.role == role)
        if is_active is not None:
            count_statement = count_statement.where(User.is_active.is_(is_active))

        total = int(self.db.scalar(count_statement) or 0)
        return items, total

    def list_storybooks(
        self,
        *,
        limit: int,
        offset: int,
        sort_desc: bool,
        user_id: UUID | None,
        status: str | None,
        start_date: date | None,
        end_date: date | None,
    ) -> tuple[list[Storybook], int]:
        statement = select(Storybook)
        if user_id is not None:
            statement = statement.where(Storybook.user_id == user_id)
        if status is not None:
            statement = statement.where(Storybook.status == status)
        if start_date is not None:
            statement = statement.where(Storybook.date >= start_date)
        if end_date is not None:
            statement = statement.where(Storybook.date <= end_date)

        order_column = Storybook.created_at
        statement = statement.order_by(order_column.desc() if sort_desc else order_column.asc())
        items = list(self.db.scalars(statement.limit(limit).offset(offset)))

        count_statement = select(func.count(Storybook.id))
        if user_id is not None:
            count_statement = count_statement.where(Storybook.user_id == user_id)
        if status is not None:
            count_statement = count_statement.where(Storybook.status == status)
        if start_date is not None:
            count_statement = count_statement.where(Storybook.date >= start_date)
        if end_date is not None:
            count_statement = count_statement.where(Storybook.date <= end_date)

        total = int(self.db.scalar(count_statement) or 0)
        return items, total

    def list_subscriptions(
        self,
        *,
        limit: int,
        offset: int,
        sort_desc: bool,
        user_id: UUID | None,
        status: str | None,
    ) -> tuple[list[Subscription], int]:
        statement = select(Subscription)
        if user_id is not None:
            statement = statement.where(Subscription.user_id == user_id)
        if status is not None:
            statement = statement.where(Subscription.status == status)

        order_column = Subscription.created_at
        statement = statement.order_by(order_column.desc() if sort_desc else order_column.asc())
        items = list(self.db.scalars(statement.limit(limit).offset(offset)))

        count_statement = select(func.count(Subscription.id))
        if user_id is not None:
            count_statement = count_statement.where(Subscription.user_id == user_id)
        if status is not None:
            count_statement = count_statement.where(Subscription.status == status)

        total = int(self.db.scalar(count_statement) or 0)
        return items, total
