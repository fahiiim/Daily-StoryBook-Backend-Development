from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.middleware.request_context import RequestContextMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(level=settings.log_level, json_logs=settings.log_json)
    logger.info("application_startup", environment=settings.app_env)
    yield
    logger.info("application_shutdown")


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.include_router(api_router)