from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.dependencies.auth import get_current_user
from app.dependencies.profile import get_profile_service
from app.models.user import User
from app.schemas.profile import (
    ClientManagementLimitsRead,
    CoachSettingsRead,
    CoachSettingsUpdateRequest,
    PasswordUpdateRequest,
    ProfileMessageResponse,
    ProfilePatchRequest,
    ProfilePutRequest,
    ProfileRead,
    SelfProfileRead,
    SelfProfileUpdateRequest,
)
from app.services.profile_service import (
    EmptyProfileUpdateError,
    InvalidCurrentPasswordError,
    InvalidProfileDataError,
    ProfileNotFoundError,
    ProfileRoleRequiredError,
    ProfileService,
)

router = APIRouter(tags=["profile"])


@router.get(
    "/profile/self",
    response_model=SelfProfileRead,
    summary="Get self user profile section",
)
def get_self_profile(
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service),
) -> SelfProfileRead:
    try:
        return profile_service.get_self_profile(current_user)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found") from exc
    except ProfileRoleRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.patch(
    "/profile/self/settings",
    response_model=SelfProfileRead,
    summary="Edit self user profile settings",
)
def patch_self_profile_settings(
    payload: SelfProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service),
) -> SelfProfileRead:
    try:
        return profile_service.update_self_profile(current_user, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found") from exc
    except ProfileRoleRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except EmptyProfileUpdateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidProfileDataError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post(
    "/profile/logout",
    response_model=ProfileMessageResponse,
    summary="Logout current user session",
)
def logout_profile(current_user: User = Depends(get_current_user)) -> ProfileMessageResponse:
    _ = current_user
    return ProfileMessageResponse(message="Logout successful. Remove the access token on the client.")


@router.delete(
    "/profile/account",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete current account permanently",
)
def delete_account(
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service),
) -> Response:
    try:
        profile_service.delete_account(current_user)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found") from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/profile/coach/settings",
    response_model=CoachSettingsRead,
    summary="Get coach settings section",
)
def get_coach_settings(
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service),
) -> CoachSettingsRead:
    try:
        return profile_service.get_coach_settings(current_user)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found") from exc
    except ProfileRoleRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.patch(
    "/profile/coach/settings",
    response_model=CoachSettingsRead,
    summary="Edit coach name phone number and biography",
)
def patch_coach_settings(
    payload: CoachSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service),
) -> CoachSettingsRead:
    try:
        return profile_service.update_coach_settings(current_user, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found") from exc
    except ProfileRoleRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except EmptyProfileUpdateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidProfileDataError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.patch(
    "/profile/coach/password",
    response_model=ProfileMessageResponse,
    summary="Update coach password",
)
def patch_coach_password(
    payload: PasswordUpdateRequest,
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service),
) -> ProfileMessageResponse:
    try:
        profile_service.update_coach_password(current_user, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found") from exc
    except ProfileRoleRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidCurrentPasswordError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ProfileMessageResponse(message="Password updated successfully")


@router.get(
    "/profile/coach/client-management-limits",
    response_model=ClientManagementLimitsRead,
    summary="Get coach client management limits",
)
def get_coach_client_management_limits(
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service),
) -> ClientManagementLimitsRead:
    try:
        return profile_service.get_coach_client_management_limits(current_user)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found") from exc
    except ProfileRoleRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


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