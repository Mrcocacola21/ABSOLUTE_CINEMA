"""Application entrypoint for the Cinema Showcase backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    configure_logging(settings.log_level)
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
        description=settings.project_description,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
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

    application.include_router(api_router)
    register_exception_handlers(application)
    return application


app = create_application()
