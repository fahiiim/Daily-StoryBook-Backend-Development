"""Pydantic schemas package."""

from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.ai import RegenerateImageRequest, RegeneratePageRequest, StorybookGenerateRequest
from app.schemas.coach_client import AddCoachClientRequest, CoachClientRead
from app.schemas.nutrition_plan import NutritionPlanCreate, NutritionPlanPut, NutritionPlanRead
from app.schemas.profile import ProfilePatchRequest, ProfilePutRequest, ProfileRead
from app.schemas.routine import RoutineCreate, RoutinePatch, RoutinePut, RoutineRead
from app.schemas.storybook import (
	StorybookGenerateResponse,
	StorybookPdfResponse,
	StorybookRead,
	StoryPageRead,
	StoryPageUpdateRequest,
)
from app.schemas.upload import ImageUploadResponse
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.schemas.workout_plan import (
	WorkoutPlanAssignRequest,
	WorkoutPlanAssignmentRead,
	WorkoutPlanCreate,
	WorkoutPlanPatch,
	WorkoutPlanPut,
	WorkoutPlanRead,
)

__all__ = [
	"AddCoachClientRequest",
	"CoachClientRead",
	"ImageUploadResponse",
	"LoginRequest",
	"RegenerateImageRequest",
	"RegeneratePageRequest",
	"NutritionPlanCreate",
	"NutritionPlanPut",
	"NutritionPlanRead",
	"ProfilePatchRequest",
	"ProfilePutRequest",
	"ProfileRead",
	"RegisterRequest",
	"RoutineCreate",
	"RoutinePatch",
	"RoutinePut",
	"RoutineRead",
	"StorybookGenerateResponse",
	"StorybookPdfResponse",
	"StorybookRead",
	"StoryPageRead",
	"StoryPageUpdateRequest",
	"StorybookGenerateRequest",
	"TokenResponse",
	"UserCreate",
	"UserRead",
	"UserUpdate",
	"WorkoutPlanAssignRequest",
	"WorkoutPlanAssignmentRead",
	"WorkoutPlanCreate",
	"WorkoutPlanPatch",
	"WorkoutPlanPut",
	"WorkoutPlanRead",
]