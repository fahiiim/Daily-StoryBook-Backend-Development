from datetime import date as dt_date
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum as SQLEnum, Float, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserRole(str, Enum):
    SELF = "SELF"
    COACH = "COACH"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(length=255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(length=255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(length=255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(length=32), nullable=True)
    # Deprecated: kept for backward compatibility, age is derived from date_of_birth in responses.
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_of_birth: Mapped[dt_date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(length=50), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    fitness_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    wake_up_time: Mapped[str | None] = mapped_column(String(length=16), nullable=True)
    bed_time: Mapped[str | None] = mapped_column(String(length=16), nullable=True)
    height: Mapped[str | None] = mapped_column(String(length=64), nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    short_bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    fitness_motivation: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    use_reference_image: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    role: Mapped[UserRole | None] = mapped_column(
        SQLEnum(UserRole, name="user_role"),
        nullable=True,
    )
    max_client_capacity: Mapped[int] = mapped_column(
        Integer,
        default=20,
        server_default=text("20"),
        nullable=False,
    )
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )