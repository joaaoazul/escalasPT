"""
The application's one and only rate limiter.

There used to be two. main.py built one with Redis storage and the configured
default limit, and then never registered SlowAPIMiddleware — so nothing ever
consulted it and RATE_LIMIT_DEFAULT did nothing at all. auth.py built a second
one with no storage argument, and that was the only limiter actually enforcing
anything. Its counters lived in process memory, so with `--workers 4` the login
limit was four times what it said, and a restart wiped it.

The key is ``request.client.host``. Uvicorn rewrites that from X-Forwarded-For
because it runs with --proxy-headers, and the proxies in front are configured
to overwrite that header rather than append to it, so a client cannot choose
its own bucket by sending one.

On Vercel there is no uvicorn in front, so ``request.client`` is not the
visitor. There the key comes from X-Forwarded-For, which Vercel's edge
overwrites with the connecting address on every request — whatever a client
sends in it is discarded before it reaches the function. That is the only
reason reading it is safe, so it is read only when SERVERLESS says we are
there.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import get_settings

settings = get_settings()


def client_address(request: Request) -> str:
    if settings.SERVERLESS:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return get_remote_address(request)


limiter = Limiter(
    key_func=client_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.REDIS_URL,
)
