from fastapi import APIRouter

from app.routers.auth import router as auth_router
from app.routers.coach_client import router as coach_client_router
from app.routers.health import router as health_router
from app.routers.profile import router as profile_router
from app.routers.upload import router as upload_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(coach_client_router)
api_router.include_router(profile_router)
api_router.include_router(upload_router)
