from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class MacroType(str, Enum):
    PROTEIN = "PROTEIN"
    CARBS = "CARBS"
    FATS = "FATS"
    FIBER = "FIBER"


class MealType(str, Enum):
    BREAKFAST = "BREAKFAST"
    LUNCH = "LUNCH"
    DINNER = "DINNER"
    SNACK = "SNACK"


class RoutineMacroLog(Base):
    __tablename__ = "routine_macro_logs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    routine_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("routines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    macro_type: Mapped[MacroType] = mapped_column(
        SQLEnum(MacroType, name="macro_type"),
        nullable=False,
        index=True,
    )
    meal_type: Mapped[MealType] = mapped_column(
        SQLEnum(MealType, name="meal_type"),
        nullable=False,
        default=MealType.SNACK,
        server_default=text("'SNACK'"),
        index=True,
    )
    food_name: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    amount_unit: Mapped[str] = mapped_column(String(length=32), nullable=False, default="grams")
    macro_grams: Mapped[float] = mapped_column(Float, nullable=False)
    kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0"))
    carbs: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0"))
    fat: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0"))
    fiber: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0"))
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
