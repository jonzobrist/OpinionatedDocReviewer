from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.api.routes import api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.middleware.csrf_guard import CsrfOriginGuardMiddleware
from app.middleware.request_log import RequestLogMiddleware
from app.middleware.rate_limit import SimpleRateLimitMiddleware

def create_app(init_db_on_startup: bool = True) -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        docs_url=f"{settings.API_PREFIX}/docs",
        redoc_url=f"{settings.API_PREFIX}/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins_list,
        allow_origin_regex=settings.CORS_ALLOW_ORIGIN_REGEX,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.cors_allow_methods_list,
        allow_headers=settings.cors_allow_headers_list,
        max_age=settings.CORS_MAX_AGE,
    )
    app.add_middleware(SimpleRateLimitMiddleware)
    app.add_middleware(CsrfOriginGuardMiddleware)
    app.add_middleware(RequestLogMiddleware)

    app.include_router(api_router, prefix=settings.API_PREFIX)

    if init_db_on_startup:
        init_db()

    return app


app = create_app()


def run() -> None:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=False,
    )


if __name__ == "__main__":
    run()
