from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        clear_contextvars()
        request_id = request.headers.get("X-Request-ID", str(uuid4()))

        bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request_failed")
            clear_contextvars()
            raise

        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
            client=request.client.host if request.client else None,
        )

        clear_contextvars()
        return response