from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("app.request")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - started) * 1000)
        x_forwarded_for = (request.headers.get("x-forwarded-for") or "-").strip() or "-"
        x_real_ip = (request.headers.get("x-real-ip") or "-").strip() or "-"
        client = request.client.host if request.client else "-"
        logger.info(
            '%s "%s %s" %s xff="%s" xri="%s" client="%s" dur_ms=%s',
            request.scope.get("http_version", "1.1"),
            request.method,
            request.url.path,
            response.status_code,
            x_forwarded_for,
            x_real_ip,
            client,
            duration_ms,
        )
        return response
