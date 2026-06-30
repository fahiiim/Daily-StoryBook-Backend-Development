"""Dependency providers package."""

from app.dependencies.auth import get_auth_service, get_current_coach, get_current_user
from app.dependencies.coach_client import get_coach_client_service
from app.dependencies.db import get_db_session
from app.dependencies.profile import get_profile_service
from app.dependencies.routine import get_routine_service
from app.dependencies.upload import get_storage_service, get_upload_service
from app.dependencies.workout_plan import get_workout_plan_service

__all__ = [
	"get_auth_service",
	"get_current_coach",
	"get_current_user",
	"get_coach_client_service",
	"get_db_session",
	"get_profile_service",
	"get_routine_service",
	"get_storage_service",
	"get_upload_service",
	"get_workout_plan_service",
]