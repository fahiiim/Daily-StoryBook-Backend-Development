from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.dependencies.ai import get_ai_service
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.ai import (
    RegenerateImageRequest,
    RegeneratePageRequest,
    StorybookGenerateRequest,
    StorybookImageRegenerateRequest,
    StorybookPageRegenerateRequest,
)
from app.services.ai_service import (
    AIService,
    AIServiceConfigError,
    AIServiceConnectionError,
    AIServiceError,
    AIServiceResponseError,
    AIServiceTimeoutError,
)

router = APIRouter(tags=["storybook"])


def _map_ai_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, AIServiceTimeoutError):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        )
    if isinstance(exc, AIServiceConnectionError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    if isinstance(exc, AIServiceResponseError):
        return HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        )
    if isinstance(exc, AIServiceConfigError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="AI service request failed",
    )


@router.post(
    "/storybook/generate",
    response_model=dict[str, Any],
    summary="Generate storybook via AI backend",
)
async def generate_storybook(
    name: str = Form(...),
    age: int = Form(...),
    gender: str = Form(...),
    fitness_goal: str = Form(...),
    wake_up_time: str = Form(...),
    bed_time: str = Form(...),
    height: str | None = Form(default=None),
    weight: float | None = Form(default=None),
    target_weight: float | None = Form(default=None),
    bio: str | None = Form(default=None),
    fitness_motivation: str | None = Form(default=None),
    image_style: str = Form(default="ghibli_animation"),
    selfie: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
) -> dict[str, Any]:
    _ = current_user
    try:
        payload = StorybookGenerateRequest(
            name=name,
            age=age,
            gender=gender,
            fitness_goal=fitness_goal,
            wake_up_time=wake_up_time,
            bed_time=bed_time,
            height=height,
            weight=weight,
            target_weight=target_weight,
            bio=bio,
            fitness_motivation=fitness_motivation,
            image_style=image_style,
        )
        return await ai_service.generate_storybook(payload=payload, selfie=selfie)
    except (AIServiceError, AIServiceResponseError) as exc:
        raise _map_ai_exception(exc) from exc


@router.get(
    "/storybook/{book_id}",
    response_model=dict[str, Any],
    summary="Get storybook via AI backend",
)
async def get_storybook(
    book_id: str,
    current_user: User = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
) -> dict[str, Any]:
    _ = current_user
    try:
        return await ai_service.get_storybook(book_id=book_id)
    except (AIServiceError, AIServiceResponseError) as exc:
        raise _map_ai_exception(exc) from exc


@router.get(
    "/storybook/page/{page_id}",
    response_model=dict[str, Any],
    summary="Get storybook page via AI backend",
)
async def get_storybook_page(
    page_id: int,
    book_id: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
) -> dict[str, Any]:
    _ = current_user
    try:
        return await ai_service.get_storybook_page(book_id=book_id, page_number=page_id)
    except (AIServiceError, AIServiceResponseError) as exc:
        raise _map_ai_exception(exc) from exc


@router.post(
    "/storybook/page/regenerate",
    response_model=dict[str, Any],
    summary="Regenerate storybook page via compact API",
)
async def regenerate_page_compact(
    payload: StorybookPageRegenerateRequest,
    current_user: User = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
) -> dict[str, Any]:
    _ = current_user
    try:
        request_payload = RegeneratePageRequest(
            title=payload.title,
            story_text=payload.story_text,
            image_prompt=payload.image_prompt,
        )
        return await ai_service.regenerate_page(
            book_id=payload.book_id,
            page_number=payload.page_id,
            payload=request_payload,
        )
    except (AIServiceError, AIServiceResponseError) as exc:
        raise _map_ai_exception(exc) from exc


@router.post(
    "/storybook/image/regenerate",
    response_model=dict[str, Any],
    summary="Regenerate storybook image via compact API",
)
async def regenerate_image_compact(
    payload: StorybookImageRegenerateRequest,
    current_user: User = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
) -> dict[str, Any]:
    _ = current_user
    try:
        request_payload = RegenerateImageRequest(
            image_prompt=payload.image_prompt,
            image_style=payload.image_style,
        )
        return await ai_service.regenerate_image(
            book_id=payload.book_id,
            page_number=payload.page_id,
            payload=request_payload,
        )
    except (AIServiceError, AIServiceResponseError) as exc:
        raise _map_ai_exception(exc) from exc


@router.post(
    "/storybook/{book_id}/page/{page_number}/regenerate",
    response_model=dict[str, Any],
    summary="Regenerate storybook page via AI backend",
)
async def regenerate_page(
    book_id: str,
    page_number: int,
    payload: RegeneratePageRequest,
    current_user: User = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
) -> dict[str, Any]:
    _ = current_user
    try:
        return await ai_service.regenerate_page(
            book_id=book_id,
            page_number=page_number,
            payload=payload,
        )
    except (AIServiceError, AIServiceResponseError) as exc:
        raise _map_ai_exception(exc) from exc


@router.post(
    "/storybook/{book_id}/page/{page_number}/image",
    response_model=dict[str, Any],
    summary="Regenerate storybook page image via AI backend",
)
async def regenerate_image(
    book_id: str,
    page_number: int,
    payload: RegenerateImageRequest,
    current_user: User = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
) -> dict[str, Any]:
    _ = current_user
    try:
        return await ai_service.regenerate_image(
            book_id=book_id,
            page_number=page_number,
            payload=payload,
        )
    except (AIServiceError, AIServiceResponseError) as exc:
        raise _map_ai_exception(exc) from exc


@router.post(
    "/storybook/{book_id}/rebuild-pdf",
    response_model=dict[str, Any],
    summary="Rebuild storybook PDF via AI backend",
)
async def rebuild_pdf(
    book_id: str,
    current_user: User = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
) -> dict[str, Any]:
    _ = current_user
    try:
        return await ai_service.rebuild_pdf(book_id=book_id)
    except (AIServiceError, AIServiceResponseError) as exc:
        raise _map_ai_exception(exc) from exc