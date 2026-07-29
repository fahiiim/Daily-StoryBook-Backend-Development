from inspect import isawaitable, signature
from pathlib import Path

from fastapi import FastAPI
from fastapi_admin.app import app as admin_app
from fastapi_admin.providers.login import UsernamePasswordProvider
from fastapi_admin.template import templates as admin_templates
from redis.asyncio import Redis
from tortoise import Tortoise

import aioredis
from app.admin import resources  # noqa: F401
from app.admin.routes import router as dashboard_router
from app.admin.tortoise_models import Admin, AdminProfile
from app.core.config import settings

_redis: Redis | None = None
_TEMPLATE_DIR = Path(__file__).with_name("templates")


def _patch_admin_template_response() -> None:
    if getattr(admin_templates, "_compat_patched", False):
        return

    template_response = admin_templates.TemplateResponse
    params = list(signature(template_response).parameters.keys())
    if not params or params[0] != "request":
        return

    def _compat_template_response(name_or_request, *args, **kwargs):
        if isinstance(name_or_request, str):
            template_name = name_or_request
            context = kwargs.pop("context", None)
            if context is None and args:
                context = args[0]
            context = context or {}
            request = context.get("request")
            if request is None:
                raise RuntimeError("Template context missing request")
            return template_response(request, template_name, context=context, **kwargs)
        return template_response(name_or_request, *args, **kwargs)

    admin_templates.TemplateResponse = _compat_template_response
    admin_templates._compat_patched = True


def _to_tortoise_db_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg"):
        return database_url.replace("postgresql+psycopg", "postgres")
    if database_url.startswith("sqlite:///"):
        # SQLAlchemy commonly uses sqlite:///./file.db while Tortoise expects sqlite://./file.db.
        return "sqlite://" + database_url[len("sqlite:///") :]
    return database_url


async def init_admin(app: FastAPI) -> None:
    _patch_admin_template_response()

    await Tortoise.init(
        db_url=_to_tortoise_db_url(settings.database_url),
        modules={"models": ["app.admin.tortoise_models"]},
    )
    await Tortoise.generate_schemas(safe=True)

    global _redis
    _redis = await aioredis.create_redis_pool(settings.redis_url, encoding="utf8")

    if not getattr(admin_app, "_dailystorybook_configured", False):
        login_provider = UsernamePasswordProvider(
            admin_model=Admin,
            login_title="DailyStoryBook administration",
            template="dailystorybook_login.html",
        )
        configure_result = admin_app.configure(
            admin_path=settings.admin_panel_path,
            language_switch=False,
            providers=[login_provider],
            redis=_redis,
            template_folders=[str(_TEMPLATE_DIR)],
        )
        if isawaitable(configure_result):
            await configure_result

        admin_app.include_router(dashboard_router)
        admin_app._dailystorybook_configured = True
    else:
        admin_app.admin_path = settings.admin_panel_path
        admin_app.redis = _redis

    app.mount(settings.admin_panel_path, admin_app)

    admin = await Admin.get_or_none(username=settings.admin_username)
    if admin is None:
        admin = await Admin.create(
            username=settings.admin_username,
            password=settings.admin_password,
        )
    elif settings.admin_reset_password:
        admin.password = settings.admin_password
        await admin.save(update_fields=["password"])

    await AdminProfile.get_or_create(
        admin_id=admin.id,
        defaults={
            "display_name": "Storybook Admin",
            "email": admin.username if "@" in admin.username else "",
        },
    )


async def shutdown_admin() -> None:
    if _redis is not None:
        close_result = _redis.close()
        if isawaitable(close_result):
            await close_result
        wait_closed = getattr(_redis, "wait_closed", None)
        if wait_closed is not None:
            wait_result = wait_closed()
            if isawaitable(wait_result):
                await wait_result
    await Tortoise.close_connections()
