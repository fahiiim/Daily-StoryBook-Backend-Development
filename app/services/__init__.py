"""Application services package."""

from app.services.auth_service import (
	AuthService,
	AuthServiceError,
	EmailAlreadyRegisteredError,
	InactiveUserError,
	InvalidCredentialsError,
)
from app.services.profile_service import (
	EmptyProfileUpdateError,
	InvalidProfileDataError,
	ProfileNotFoundError,
	ProfileService,
	ProfileServiceError,
)
from app.services.coach_client_service import (
	CoachClientNotFoundError,
	CoachClientRelationshipExistsError,
	CoachClientRelationshipNotFoundError,
	CoachClientService,
	CoachClientServiceError,
	CoachRoleRequiredError,
	InvalidCoachClientAssignmentError,
)
from app.services.storage_service import (
	ImageTooLargeError,
	StorageConfigurationError,
	StorageService,
	StorageServiceError,
	UnsupportedImageTypeError,
)
from app.services.upload_service import (
	UploadService,
	UploadServiceError,
	UploadUserNotFoundError,
)
from app.services.routine_service import (
	EmptyRoutineUpdateError,
	RoutineAlreadyExistsError,
	RoutineNotFoundError,
	RoutineService,
	RoutineServiceError,
)

__all__ = [
	"AuthService",
	"AuthServiceError",
	"EmailAlreadyRegisteredError",
	"InactiveUserError",
	"InvalidCredentialsError",
	"EmptyProfileUpdateError",
	"InvalidProfileDataError",
	"ProfileNotFoundError",
	"ProfileService",
	"ProfileServiceError",
	"CoachClientNotFoundError",
	"CoachClientRelationshipExistsError",
	"CoachClientRelationshipNotFoundError",
	"CoachClientService",
	"CoachClientServiceError",
	"CoachRoleRequiredError",
	"InvalidCoachClientAssignmentError",
	"ImageTooLargeError",
	"StorageConfigurationError",
	"StorageService",
	"StorageServiceError",
	"UnsupportedImageTypeError",
	"UploadService",
	"UploadServiceError",
	"UploadUserNotFoundError",
	"EmptyRoutineUpdateError",
	"RoutineAlreadyExistsError",
	"RoutineNotFoundError",
	"RoutineService",
	"RoutineServiceError",
]