from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.admin.setup import init_admin, shutdown_admin
from app.api.router import api_router
from app.core.config import BASE_DIR, settings
from app.core.logging import configure_logging, get_logger
from app.middleware.request_context import RequestContextMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(level=settings.log_level, json_logs=settings.log_json)
    logger.info("application_startup", environment=settings.app_env)
    await init_admin(app)
    yield
    await shutdown_admin()
    logger.info("application_shutdown")


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    lifespan=lifespan,
)

if settings.storage_backend.strip().lower() == "local":
    media_root = BASE_DIR / settings.local_storage_dir
    media_root.mkdir(parents=True, exist_ok=True)

    media_url_prefix = settings.local_media_url_prefix.strip()
    if not media_url_prefix.startswith("/"):
        media_url_prefix = f"/{media_url_prefix}"

    app.mount(
        media_url_prefix,
        StaticFiles(directory=str(media_root)),
        name="media",
    )

app.add_middleware(RequestContextMiddleware)
app.include_router(api_router)