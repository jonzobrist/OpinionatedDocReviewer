from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import settings


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory fixed-window limiter.

    This is intentionally simple for single-instance deployments.
    For multi-node/cloud scale, use a shared Redis-backed limiter.
    """

    def __init__(self, app):
        super().__init__(app)
        self._lock = threading.Lock()
        self._buckets: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    def _is_exempt(self, request: Request) -> bool:
        if request.method == "OPTIONS":
            return True
        path = request.url.path
        return path.endswith("/health") or path.endswith("/openapi.json")

    def _key(self, request: Request) -> str:
        xfwd = request.headers.get("x-forwarded-for", "")
        client_ip = xfwd.split(",")[0].strip() if xfwd else (request.client.host if request.client else "unknown")
        return f"{client_ip}:{request.url.path}"

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.RATE_LIMIT_ENABLED or self._is_exempt(request):
            return await call_next(request)

        window_seconds = max(1, settings.RATE_LIMIT_WINDOW_SECONDS)
        limit = max(1, settings.RATE_LIMIT_MAX_REQUESTS)
        now = int(time.time())
        window = now // window_seconds
        key = self._key(request)
        with self._lock:
            count, seen_window = self._buckets.get(key, (0, window))
            if seen_window != window:
                count, seen_window = 0, window
            count += 1
            self._buckets[key] = (count, seen_window)
            if count > limit:
                retry_after = window_seconds - (now % window_seconds)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": str(max(1, retry_after))},
                )

        return await call_next(request)
