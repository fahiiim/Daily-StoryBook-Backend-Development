from fastapi import FastAPI
from fastapi_admin.app import app as admin_app
from fastapi_admin.providers.login import UsernamePasswordProvider
from fastapi_admin.utils import hash_password
from tortoise import Tortoise

import aioredis

from app.admin import resources  # noqa: F401
from app.admin.tortoise_models import Admin
from app.core.config import settings

_redis = None


def _to_tortoise_db_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg"):
        return database_url.replace("postgresql+psycopg", "postgres")
    return database_url


async def init_admin(app: FastAPI) -> None:
    await Tortoise.init(
        db_url=_to_tortoise_db_url(settings.database_url),
        modules={"models": ["app.admin.tortoise_models"]},
    )
    await Tortoise.generate_schemas(safe=True)

    global _redis
    _redis = await aioredis.create_redis_pool(settings.redis_url, encoding="utf8")

    login_provider = UsernamePasswordProvider(admin_model=Admin)
    admin_app.configure(
        logo_url="https://preview.tabler.io/static/logo-white.svg",
        providers=[login_provider],
        redis=_redis,
    )

    app.mount(settings.admin_panel_path, admin_app)

    exists = await Admin.exists(username=settings.admin_username)
    if not exists:
        await Admin.create(
            username=settings.admin_username,
            password=hash_password(settings.admin_password),
        )


async def shutdown_admin() -> None:
    if _redis is not None:
        _redis.close()
        await _redis.wait_closed()
    await Tortoise.close_connections()
