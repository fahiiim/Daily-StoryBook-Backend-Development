from secrets import randbelow

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.dependencies.auth import get_current_user
from app.dependencies.verification_flow import get_verification_flow_service
from app.models.user import User
from app.schemas.user import UserRead
from app.schemas.verification import (
    ForgotPasswordRequest,
    MessageResponse,
    PasswordResetRequest,
    VerificationCodeRequest,
)
from app.services.verification_flow_service import (
    VerificationFlowService,
    VerificationUserNotFoundError,
)
from app.services.verification_service import (
    ExpiredVerificationCodeError,
    InvalidVerificationCodeError,
)

router = APIRouter(tags=["verification"])


@router.post(
    "/email/send-verification",
    summary="Send email verification code",
)
def send_email_verification(
    current_user: User = Depends(get_current_user),
    verification_flow_service: VerificationFlowService = Depends(get_verification_flow_service),
) -> dict[str, str]:
    try:
        code = verification_flow_service.send_email_verification(current_user=current_user)
    except VerificationUserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    response = {"message": "Verification code sent"}
    # WARNING: debug_code must only be returned in development for local testing.
    if settings.app_env == "development":
        response["debug_code"] = code
    return response


@router.post(
    "/email/verify",
    response_model=UserRead,
    summary="Verify email with code",
)
def verify_email(
    payload: VerificationCodeRequest,
    current_user: User = Depends(get_current_user),
    verification_flow_service: VerificationFlowService = Depends(get_verification_flow_service),
) -> UserRead:
    try:
        user = verification_flow_service.verify_email(current_user=current_user, code=payload.code)
    except VerificationUserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExpiredVerificationCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidVerificationCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return UserRead.model_validate(user)


@router.post(
    "/password/forgot",
    summary="Request password reset code",
)
def forgot_password(
    payload: ForgotPasswordRequest,
    verification_flow_service: VerificationFlowService = Depends(get_verification_flow_service),
) -> dict[str, str]:
    code = verification_flow_service.request_password_reset(email=str(payload.email))
    response = {"message": "If an account exists for this email, a reset code has been sent"}

    # WARNING: debug_code must only be returned in development for local testing.
    if settings.app_env == "development":
        # Preserve anti-enumeration behavior by returning a code-shaped value even when user is absent.
        response["debug_code"] = code or f"{randbelow(1_000_000):06d}"
    return response


@router.post(
    "/password/reset",
    response_model=MessageResponse,
    summary="Reset password with verification code",
)
def reset_password(
    payload: PasswordResetRequest,
    verification_flow_service: VerificationFlowService = Depends(get_verification_flow_service),
) -> MessageResponse:
    try:
        verification_flow_service.reset_password(
            email=str(payload.email),
            code=payload.code,
            new_password=payload.new_password,
        )
    except ExpiredVerificationCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidVerificationCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or verification code",
        ) from exc

    return MessageResponse(message="Password reset successful")
