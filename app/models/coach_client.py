from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum as SQLEnum, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CoachClientStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class CoachClient(Base):
    __tablename__ = "coach_client"
    __table_args__ = (
        UniqueConstraint("coach_id", "client_id", name="uq_coach_client_pair"),
        CheckConstraint("coach_id <> client_id", name="ck_coach_client_not_self"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    coach_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    personalized_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    assign_initial_plan: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    status: Mapped[CoachClientStatus] = mapped_column(
        SQLEnum(CoachClientStatus, name="coach_client_status"),
        default=CoachClientStatus.ACCEPTED,
        server_default=text("'ACCEPTED'"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )