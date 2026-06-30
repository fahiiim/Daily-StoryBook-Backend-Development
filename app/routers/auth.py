from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_auth_service, get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.auth_service import (
    AuthService,
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
)

router = APIRouter(tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={409: {"description": "Email already registered"}},
)
def register_user(
    payload: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    try:
        return auth_service.register_user(payload)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc


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