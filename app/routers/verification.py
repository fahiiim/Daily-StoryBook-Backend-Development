from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.verification_flow import get_verification_flow_service
from app.schemas.user import UserRead
from app.schemas.verification import (
    EmailVerificationConfirmRequest,
    EmailVerificationRequest,
    ForgotPasswordRequest,
    MessageResponse,
    OptionalOtpResponse,
    OtpResponse,
    PasswordResetRequest,
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
    response_model=OtpResponse,
    summary="Send email verification code",
)
def send_email_verification(
    payload: EmailVerificationRequest,
    verification_flow_service: VerificationFlowService = Depends(get_verification_flow_service),
) -> OtpResponse:
    try:
        code = verification_flow_service.send_email_verification_by_email(email=str(payload.email))
    except VerificationUserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return OtpResponse(message="Verification code sent", otp=code)


@router.post(
    "/email/verify",
    response_model=UserRead,
    summary="Verify email with code",
)
def verify_email(
    payload: EmailVerificationConfirmRequest,
    verification_flow_service: VerificationFlowService = Depends(get_verification_flow_service),
) -> UserRead:
    try:
        user = verification_flow_service.verify_email_by_email(
            email=str(payload.email),
            code=payload.code,
        )
    except VerificationUserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExpiredVerificationCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidVerificationCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return UserRead.model_validate(user)


@router.post(
    "/password/forgot",
    response_model=OptionalOtpResponse,
    response_model_exclude_none=True,
    summary="Request password reset code",
)
def forgot_password(
    payload: ForgotPasswordRequest,
    verification_flow_service: VerificationFlowService = Depends(get_verification_flow_service),
) -> OptionalOtpResponse:
    code = verification_flow_service.request_password_reset(email=str(payload.email))
    return OptionalOtpResponse(
        message="If an account exists for this email, a reset code has been sent",
        otp=code,
    )


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
