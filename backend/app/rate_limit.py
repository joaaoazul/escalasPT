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
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.REDIS_URL,
)
