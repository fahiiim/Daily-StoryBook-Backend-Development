from fastapi import FastAPI
from fastapi_admin.app import app as admin_app
from fastapi_admin.providers.login import UsernamePasswordProvider
from fastapi_admin.template import templates as admin_templates
from fastapi_admin.utils import hash_password
from starlette.responses import RedirectResponse
from tortoise import Tortoise
from inspect import isawaitable, signature

import aioredis

from app.admin import resources  # noqa: F401
from app.admin.tortoise_models import Admin
from app.core.config import settings

_redis = None


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
    setattr(admin_templates, "_compat_patched", True)


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

    login_provider = UsernamePasswordProvider(admin_model=Admin)
    configure_result = admin_app.configure(
        logo_url="https://preview.tabler.io/static/logo-white.svg",
        providers=[login_provider],
        redis=_redis,
    )
    if isawaitable(configure_result):
        await configure_result

    if not any(getattr(route, "path", None) == "/" for route in admin_app.routes):
        @admin_app.get("/")
        async def _admin_root_redirect():
            return RedirectResponse(url=f"{settings.admin_panel_path}/login")

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
