from datetime import date as dt_date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import EmailStr, ValidationError

from app.dependencies.auth import get_auth_service, get_current_user
from app.dependencies.upload import get_upload_service
from app.dependencies.verification_flow import get_verification_flow_service
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    RegistrationInfoPatchRequest,
    RegistrationInfoResponse,
    TokenResponse,
)
from app.schemas.user import UserRead
from app.services.auth_service import (
    AuthService,
    EmailNotVerifiedError,
    EmailAlreadyRegisteredError,
    EmptyRegistrationInfoUpdateError,
    InactiveUserError,
    InvalidCredentialsError,
)
from app.services.storage_service import (
    ImageTooLargeError,
    StorageConfigurationError,
    StorageServiceError,
    UnsupportedImageTypeError,
)
from app.services.upload_service import UploadService, UploadUserNotFoundError
from app.services.verification_flow_service import VerificationFlowService

router = APIRouter(tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={409: {"description": "Email already registered"}},
)
async def register_user(
    email: EmailStr = Form(...),
    password: str = Form(..., min_length=8, max_length=255),
    full_name: str = Form(..., min_length=1, max_length=255),
    role: Literal["SELF", "COACH"] = Form(...),
    date_of_birth: dt_date | None = Form(default=None),
    gender: str | None = Form(default=None),
    occupation: str | None = Form(default=None),
    fitness_goal: str | None = Form(default=None),
    wake_up_time: str | None = Form(default=None),
    bed_time: str | None = Form(default=None),
    height: str | None = Form(default=None),
    weight: float | None = Form(default=None),
    target_weight: float | None = Form(default=None),
    short_bio: str | None = Form(default=None),
    fitness_motivation: str | None = Form(default=None),
    profile_image: UploadFile | None = File(default=None),
    reference_image: UploadFile | None = File(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    upload_service: UploadService = Depends(get_upload_service),
    verification_flow_service: VerificationFlowService = Depends(get_verification_flow_service),
) -> RegisterResponse:
    try:
        payload = RegisterRequest(
            email=str(email),
            password=password,
            full_name=full_name,
            role=role,
            date_of_birth=date_of_birth,
            gender=gender,
            occupation=occupation,
            fitness_goal=fitness_goal,
            wake_up_time=wake_up_time,
            bed_time=bed_time,
            height=height,
            weight=weight,
            target_weight=target_weight,
            short_bio=short_bio,
            fitness_motivation=fitness_motivation,
        )
        user = auth_service.register_user(payload)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    try:
        if profile_image is not None:
            user.profile_image = await upload_service.upload_profile_image(user_id=user.id, file=profile_image)
        if reference_image is not None:
            user.reference_image = await upload_service.upload_reference_image(user_id=user.id, file=reference_image)
    except UnsupportedImageTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported image type") from exc
    except ImageTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Image exceeds maximum allowed size") from exc
    except UploadUserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except StorageServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload image") from exc

    verification_flow_service.send_email_verification(current_user=user)
    return RegisterResponse(user=UserRead.model_validate(user))


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


@router.patch(
    "/auth/registration-info",
    response_model=RegistrationInfoResponse,
    summary="Update registered user information for storybook generation",
)
async def patch_registration_info(
    full_name: str | None = Form(default=None),
    date_of_birth: dt_date | None = Form(default=None),
    gender: str | None = Form(default=None),
    occupation: str | None = Form(default=None),
    fitness_goal: str | None = Form(default=None),
    wake_up_time: str | None = Form(default=None),
    bed_time: str | None = Form(default=None),
    height: str | None = Form(default=None),
    weight: float | None = Form(default=None),
    target_weight: float | None = Form(default=None),
    short_bio: str | None = Form(default=None),
    fitness_motivation: str | None = Form(default=None),
    profile_image: UploadFile | None = File(default=None),
    reference_image: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    upload_service: UploadService = Depends(get_upload_service),
) -> RegistrationInfoResponse:
    raw_payload = {
        "full_name": full_name,
        "date_of_birth": date_of_birth,
        "gender": gender,
        "occupation": occupation,
        "fitness_goal": fitness_goal,
        "wake_up_time": wake_up_time,
        "bed_time": bed_time,
        "height": height,
        "weight": weight,
        "target_weight": target_weight,
        "short_bio": short_bio,
        "fitness_motivation": fitness_motivation,
    }
    payload_data = {field_name: value for field_name, value in raw_payload.items() if value is not None}

    if not payload_data and profile_image is None and reference_image is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No registration information fields were provided",
        )

    try:
        user = auth_service.get_user(current_user=current_user)
        if payload_data:
            payload = RegistrationInfoPatchRequest(**payload_data)
            user = auth_service.update_registration_info(current_user=current_user, payload=payload)

        if profile_image is not None:
            await upload_service.upload_profile_image(user_id=current_user.id, file=profile_image)
        if reference_image is not None:
            await upload_service.upload_reference_image(user_id=current_user.id, file=reference_image)

        if profile_image is not None or reference_image is not None:
            user = auth_service.get_user(current_user=current_user)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except EmptyRegistrationInfoUpdateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    except UnsupportedImageTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported image type") from exc
    except ImageTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Image exceeds maximum allowed size") from exc
    except UploadUserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    except StorageConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except StorageServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload image") from exc

    return RegistrationInfoResponse(user=UserRead.model_validate(user))


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