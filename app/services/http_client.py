from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx


@asynccontextmanager
async def get_http_client(timeout_seconds: float = 10.0) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        yield client