from __future__ import annotations

import re

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import settings


class CsrfOriginGuardMiddleware(BaseHTTPMiddleware):
    """Origin guard for mutating browser requests.

    If an Origin header is present on mutating requests, require it to match
    configured CORS allow list/regex.
    """

    _MUTATING = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.CSRF_ENFORCE_ORIGIN:
            return await call_next(request)
        if request.method.upper() not in self._MUTATING:
            return await call_next(request)

        origin = (request.headers.get("origin") or "").strip()
        if not origin:
            return await call_next(request)

        allowed = set(settings.cors_allow_origins_list)
        if origin in allowed:
            return await call_next(request)

        origin_regex = (settings.CORS_ALLOW_ORIGIN_REGEX or "").strip()
        if origin_regex and re.match(origin_regex, origin):
            return await call_next(request)

        return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
