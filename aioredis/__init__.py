from __future__ import annotations

from typing import Any, Awaitable, Callable

from redis.asyncio import Redis, from_url
from redis.asyncio.client import Redis as StrictRedis


def _attach_wait_closed(client: Redis) -> Redis:
    async def wait_closed() -> None:
        await client.connection_pool.disconnect()

    setattr(client, "wait_closed", wait_closed)
    return client


async def create_redis_pool(url: str, encoding: str = "utf8", **kwargs: Any) -> Redis:
    client = from_url(url, encoding=encoding, decode_responses=True, **kwargs)
    return _attach_wait_closed(client)


__all__ = ["Redis", "StrictRedis", "create_redis_pool"]
