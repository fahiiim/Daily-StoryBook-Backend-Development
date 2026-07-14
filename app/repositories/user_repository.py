from uuid import UUID
from typing import Any
from datetime import date as dt_date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return self.db.scalar(statement)

    def get_by_username(self, username: str) -> User | None:
        statement = select(User).where(User.username == username)
        return self.db.scalar(statement)

    def get_by_id(self, user_id: UUID) -> User | None:
        statement = select(User).where(User.id == user_id)
        return self.db.scalar(statement)

    def create(
        self,
        *,
        username: str,
        email: str,
        hashed_password: str,
        full_name: str,
        age: int | None,
        date_of_birth: dt_date | None,
        gender: str | None,
        occupation: str | None,
        fitness_goal: str | None,
        wake_up_time: str | None,
        bed_time: str | None,
        height: str | None,
        weight: float | None,
        target_weight: float | None,
        short_bio: str | None,
        fitness_motivation: str | None,
        bio: str | None,
        profile_image: str | None,
        reference_image: str | None,
        use_reference_image: bool,
        role: UserRole | None,
        is_active: bool,
        is_email_verified: bool,
        phone_number: str | None = None,
    ) -> User:
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            phone_number=phone_number,
            age=age,
            date_of_birth=date_of_birth,
            gender=gender,
            occupation=occupation,
            fitness_goal=fitness_goal,
            wake_up_time=wake_up_time,
            bed_time=bed_time,
            height=height,
            weight=weight,
            target_weight=target_weight,
            short_bio=short_bio,
            fitness_motivation=fitness_motivation,
            bio=bio,
            profile_image=profile_image,
            reference_image=reference_image,
            use_reference_image=use_reference_image,
            role=role,
            is_active=is_active,
            is_email_verified=is_email_verified,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, *, user: User) -> None:
        self.db.delete(user)
        self.db.commit()

    def update_fields(self, *, user: User, updates: dict[str, Any]) -> User:
        for field_name, value in updates.items():
            setattr(user, field_name, value)

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user