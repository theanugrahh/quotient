from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import PROJECT_ROOT, settings
from app.database import Base, engine
from app.errors import register_exception_handlers
from app.logging_config import configure_logging, get_logger
from app.middleware import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.routers import admin, auth, billing, clients, files, invoices, public, webhooks

logger = get_logger("app.main")

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
    if settings.database_url.startswith("sqlite"):
        Path(settings.database_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    logger.info("startup environment=%s provider=%s", settings.environment, settings.payments_provider)
    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Quotient API",
        description="Quotes, invoices and payments for independent studios.",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", settings.csrf_header_name, "X-Request-Id"],
        expose_headers=["X-Request-Id"],
        max_age=600,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    register_exception_handlers(app)

    prefix = settings.api_prefix
    app.include_router(auth.router, prefix=prefix)
    app.include_router(clients.router, prefix=prefix)
    app.include_router(invoices.router, prefix=prefix)
    app.include_router(files.router, prefix=prefix)
    app.include_router(public.router, prefix=prefix)
    app.include_router(billing.router, prefix=prefix)
    app.include_router(webhooks.router, prefix=prefix)
    app.include_router(admin.router, prefix=prefix)

    @app.get(f"{prefix}/health", tags=["system"])
    def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "service": settings.app_name})

    if FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str) -> FileResponse:
            candidate = FRONTEND_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
