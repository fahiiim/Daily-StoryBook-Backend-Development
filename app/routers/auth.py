from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_auth_service, get_current_user
from app.dependencies.verification_flow import get_verification_flow_service
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, RegisterResponse, TokenResponse
from app.schemas.user import UserRead
from app.services.auth_service import (
    AuthService,
    EmailNotVerifiedError,
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    UsernameAlreadyTakenError,
)
from app.services.verification_flow_service import VerificationFlowService

router = APIRouter(tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={409: {"description": "Email already registered"}},
)
def register_user(
    payload: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
    verification_flow_service: VerificationFlowService = Depends(get_verification_flow_service),
) -> RegisterResponse:
    try:
        user = auth_service.register_user(payload)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    except UsernameAlreadyTakenError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    otp = verification_flow_service.send_email_verification(current_user=user)
    return RegisterResponse(user=UserRead.model_validate(user), otp=otp)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get access token",
    responses={
        401: {
            "description": "Invalid email or password",
            "headers": {"WWW-Authenticate": {"schema": {"type": "string"}}},
        },
        403: {"description": "Inactive user account"},
    },
)
def login_user(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        token = auth_service.login_user(payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        ) from exc
    except EmailNotVerifiedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verify your email before logging in",
        ) from exc

    return TokenResponse(access_token=token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get authenticated user profile",
    responses={
        401: {
            "description": "Missing or invalid token",
            "headers": {"WWW-Authenticate": {"schema": {"type": "string"}}},
        },
        403: {"description": "Inactive user account"},
    },
)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user