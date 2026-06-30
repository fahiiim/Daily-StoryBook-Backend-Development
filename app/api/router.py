from fastapi import APIRouter

from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.profile import router as profile_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(profile_router)
