from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine_kwargs: dict[str, object] = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,
}

if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}


engine = create_engine(
    settings.database_url,
    **engine_kwargs,
)