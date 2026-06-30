from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return self.db.scalar(statement)

    def get_by_id(self, user_id: UUID) -> User | None:
        statement = select(User).where(User.id == user_id)
        return self.db.scalar(statement)

    def create(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: str,
        age: int | None,
        gender: str | None,
        occupation: str | None,
        fitness_goal: str | None,
        profile_image: str | None,
        reference_image: str | None,
        role: UserRole,
        is_active: bool,
    ) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            age=age,
            gender=gender,
            occupation=occupation,
            fitness_goal=fitness_goal,
            profile_image=profile_image,
            reference_image=reference_image,
            role=role,
            is_active=is_active,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user