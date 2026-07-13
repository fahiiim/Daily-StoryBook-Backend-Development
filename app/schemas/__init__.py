"""Pydantic schemas package."""

from app.schemas.auth import LoginRequest, RegisterRequest, RegisterResponse, TokenResponse
from app.schemas.ai import RegenerateImageRequest, RegeneratePageRequest, StorybookGenerateRequest
from app.schemas.admin import (
	AdminDashboardResponse,
	AdminStorybookListResponse,
	AdminSubscriptionListResponse,
	AdminUserListResponse,
)
from app.schemas.coach_client import AddCoachClientRequest, CoachClientRead
from app.schemas.dashboard import CoachDashboardResponse, DashboardResponse
from app.schemas.notification import (
	NotificationListResponse,
	NotificationRead,
	NotificationUnreadCountResponse,
)
from app.schemas.subscription import SubscriptionRead
from app.schemas.nutrition_plan import NutritionPlanCreate, NutritionPlanPut, NutritionPlanRead
from app.schemas.profile import ProfilePatchRequest, ProfilePutRequest, ProfileRead
from app.schemas.routine import RoutineCreate, RoutinePatch, RoutinePut, RoutineRead
from app.schemas.storybook import (
	StorybookGenerateResponse,
	StorybookPdfResponse,
	StorybookRead,
	StorybookStatusResponse,
	StoryPageRead,
	StoryPageUpdateRequest,
)
from app.schemas.weekly_summary import (
	WeeklySummaryGenerateRequest,
	WeeklySummaryGenerateResponse,
	WeeklySummaryHistoryResponse,
	WeeklySummaryRead,
)
from app.schemas.verification import (
	EmailVerificationRequest,
	EmailVerificationConfirmRequest,
	ForgotPasswordRequest,
	MessageResponse,
	OptionalOtpResponse,
	OtpResponse,
	PasswordResetRequest,
	VerificationCodeRequest,
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
	"CoachDashboardResponse",
	"DashboardResponse",
	"AdminDashboardResponse",
	"AdminStorybookListResponse",
	"AdminSubscriptionListResponse",
	"AdminUserListResponse",
	"NotificationListResponse",
	"NotificationRead",
	"NotificationUnreadCountResponse",
	"SubscriptionRead",
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
	"RegisterResponse",
	"RoutineCreate",
	"RoutinePatch",
	"RoutinePut",
	"RoutineRead",
	"StorybookGenerateResponse",
	"StorybookPdfResponse",
	"StorybookRead",
	"StorybookStatusResponse",
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
	"WeeklySummaryGenerateRequest",
	"WeeklySummaryGenerateResponse",
	"WeeklySummaryHistoryResponse",
	"WeeklySummaryRead",
	"EmailVerificationRequest",
	"EmailVerificationConfirmRequest",
	"ForgotPasswordRequest",
	"MessageResponse",
	"OptionalOtpResponse",
	"OtpResponse",
	"PasswordResetRequest",
	"VerificationCodeRequest",
]