from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import settings


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose declared body size exceeds MAX_REQUEST_BODY_BYTES.

    Relies on the Content-Length header for a cheap fast-path check so we do
    not buffer large bodies. Requests without a Content-Length (chunked
    transfer encoding, streaming uploads) fall through to downstream
    per-route validation, which is where schema-level size limits apply for
    fields like document content.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        limit = settings.MAX_REQUEST_BODY_BYTES
        if limit and limit > 0:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    declared = int(content_length)
                except ValueError:
                    return JSONResponse(
                        {"detail": "Invalid Content-Length header"},
                        status_code=400,
                    )
                if declared > limit:
                    return JSONResponse(
                        {"detail": "Request body too large"},
                        status_code=413,
                    )
        return await call_next(request)
