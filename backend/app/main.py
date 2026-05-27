"""Application entrypoint for the Cinema Showcase backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.docs import API_TAGS, OPENAPI_DESCRIPTION, PROJECT_REPOSITORY_URL, SWAGGER_UI_PARAMETERS
from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.database import mongodb_manager
from app.middleware.request_logging import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize and release infrastructure resources for the API lifecycle."""
    settings = get_settings()
    configure_logging(
        settings.log_level,
        log_format=settings.log_format,
        file_enabled=settings.log_file_enabled,
        file_level=settings.log_file_level,
        payments_level=settings.payment_log_level,
        audit_level=settings.audit_log_level,
        app_log_file=settings.app_log_file,
        payments_log_file=settings.payments_log_file,
        audit_log_file=settings.audit_log_file,
        max_bytes=settings.log_rotation_max_bytes,
        backup_count=settings.log_rotation_backup_count,
    )
    await mongodb_manager.connect()
    try:
        yield
    finally:
        await mongodb_manager.disconnect()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()
    application = FastAPI(
        title=settings.project_name,
        version=settings.project_version,
        description=OPENAPI_DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=API_TAGS,
        contact={
            "name": "Cinema Showcase Project Repository",
            "url": PROJECT_REPOSITORY_URL,
        },
        swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestLoggingMiddleware)

    media_root = Path(settings.media_root)
    media_root.mkdir(parents=True, exist_ok=True)
    application.mount(settings.media_url, StaticFiles(directory=media_root), name="media")

    application.include_router(api_router)
    register_exception_handlers(application)
    return application


app = create_application()
