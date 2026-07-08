from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.dependencies.auth import get_current_onboarded_user
from app.dependencies.upload import get_upload_service
from app.models.user import User
from app.schemas.upload import ImageUploadResponse
from app.services.storage_service import (
    ImageTooLargeError,
    StorageConfigurationError,
    StorageServiceError,
    UnsupportedImageTypeError,
)
from app.services.upload_service import UploadService, UploadUserNotFoundError

router = APIRouter(tags=["upload"])


@router.post(
    "/upload/profile",
    response_model=ImageUploadResponse,
    summary="Upload profile image",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "User not found"},
        413: {"description": "Image too large"},
        415: {"description": "Unsupported image type"},
    },
)
async def upload_profile_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_onboarded_user),
    upload_service: UploadService = Depends(get_upload_service),
) -> ImageUploadResponse:
    try:
        image_url = await upload_service.upload_profile_image(user_id=current_user.id, file=file)
    except UnsupportedImageTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported image type",
        ) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Image exceeds maximum allowed size",
        ) from exc
    except UploadUserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
    except StorageConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except StorageServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image",
        ) from exc

    return ImageUploadResponse(url=image_url)


@router.post(
    "/upload/reference",
    response_model=ImageUploadResponse,
    summary="Upload reference image",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "User not found"},
        413: {"description": "Image too large"},
        415: {"description": "Unsupported image type"},
    },
)
async def upload_reference_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_onboarded_user),
    upload_service: UploadService = Depends(get_upload_service),
) -> ImageUploadResponse:
    try:
        image_url = await upload_service.upload_reference_image(user_id=current_user.id, file=file)
    except UnsupportedImageTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported image type",
        ) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Image exceeds maximum allowed size",
        ) from exc
    except UploadUserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
    except StorageConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except StorageServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image",
        ) from exc

    return ImageUploadResponse(url=image_url)