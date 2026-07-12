from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Routine(Base):
    __tablename__ = "routines"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_routines_user_date"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    workout: Mapped[str | None] = mapped_column(Text, nullable=True)
    meals: Mapped[str | None] = mapped_column(Text, nullable=True)
    meals_kcal: Mapped[float | None] = mapped_column(Float, nullable=True)
    goal_kcal: Mapped[float | None] = mapped_column(Float, nullable=True)
    goal_protein: Mapped[float | None] = mapped_column(Float, nullable=True)
    goal_carbs: Mapped[float | None] = mapped_column(Float, nullable=True)
    goal_fats: Mapped[float | None] = mapped_column(Float, nullable=True)
    goal_fiber: Mapped[float | None] = mapped_column(Float, nullable=True)
    intake_protein: Mapped[float | None] = mapped_column(Float, nullable=True)
    intake_carbs: Mapped[float | None] = mapped_column(Float, nullable=True)
    intake_fats: Mapped[float | None] = mapped_column(Float, nullable=True)
    intake_fiber: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_intake: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_status: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
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