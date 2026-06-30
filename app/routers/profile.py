from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.dependencies.profile import get_profile_service
from app.models.user import User
from app.schemas.profile import ProfilePatchRequest, ProfilePutRequest, ProfileRead
from app.services.profile_service import (
    EmptyProfileUpdateError,
    InvalidProfileDataError,
    ProfileNotFoundError,
    ProfileService,
)

router = APIRouter(tags=["profile"])


@router.get(
    "/profile",
    response_model=ProfileRead,
    summary="Get authenticated user profile",
)
def get_profile(
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service),
) -> User:
    try:
        return profile_service.get_profile(current_user)
    except ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        ) from exc


@router.put(
    "/profile",
    response_model=ProfileRead,
    summary="Replace authenticated user profile",
)
def put_profile(
    payload: ProfilePutRequest,
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service),
) -> User:
    try:
        return profile_service.replace_profile(current_user, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        ) from exc
    except InvalidProfileDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.patch(
    "/profile",
    response_model=ProfileRead,
    summary="Partially update authenticated user profile",
)
def patch_profile(
    payload: ProfilePatchRequest,
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service),
) -> User:
    try:
        return profile_service.patch_profile(current_user, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        ) from exc
    except EmptyProfileUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except InvalidProfileDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc