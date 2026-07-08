from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.dependencies.onboarding import get_onboarding_service
from app.models.user import User
from app.schemas.onboarding import OnboardingRoleRequest
from app.schemas.user import UserRead
from app.services.onboarding_service import (
    OnboardingService,
    OnboardingUserNotFoundError,
    RoleAlreadySelectedError,
)

router = APIRouter(tags=["onboarding"])


@router.patch(
    "/onboarding/role",
    response_model=UserRead,
    summary="Set initial onboarding role",
)
def set_onboarding_role(
    payload: OnboardingRoleRequest,
    current_user: User = Depends(get_current_user),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> User:
    try:
        return onboarding_service.set_initial_role(current_user=current_user, payload=payload)
    except RoleAlreadySelectedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OnboardingUserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
