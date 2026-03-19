"""Root API router composition."""

from fastapi import APIRouter

from app.api.routers import admin, auth, health, movies, schedule, sessions, tickets, users
from app.core.config import get_settings

settings = get_settings()

api_router = APIRouter(prefix=settings.api_v1_prefix)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(movies.router)
api_router.include_router(schedule.router)
api_router.include_router(sessions.router)
api_router.include_router(tickets.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
