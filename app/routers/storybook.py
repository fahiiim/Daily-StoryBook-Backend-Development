import json
from dataclasses import replace
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status

from app.dependencies.auth import get_current_coach, get_current_onboarded_user
from app.db.session import SessionLocal
from app.dependencies.storybook import get_storybook_service
from app.models.user import User
from app.schemas.ai import RegenerateImageRequest, RegeneratePageRequest
from app.schemas.storybook import (
    CoachClientStorybookStatusRead,
    StorybookGenerateResponse,
    StorybookPdfResponse,
    StorybookRead,
    StoryPageRead,
    StoryPageUpdateRequest,
    StorybookStatusResponse,
)
from app.services.ai_service import (
    AIService,
    AIServiceConfigError,
    AIServiceConnectionError,
    AIServiceError,
    AIServiceResponseError,
    AIServiceTimeoutError,
)
from app.services.storybook_service import (
    StorybookAccessError,
    StorybookGenerationJob,
    StorybookNotFoundError,
    StorybookService,
    StorybookValidationError,
    StoryPageNotFoundError,
)
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.storybook_repository import StorybookRepository, StoryPageRepository
from app.repositories.user_repository import UserRepository

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
    response_model=StorybookGenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate storybook",
    include_in_schema=False,
)
async def generate_storybook(
    background_tasks: BackgroundTasks,
    client_id: str = Form(...),
    wake_up_time: str | None = Form(default=None),
    bed_time: str | None = Form(default=None),
    selfie: UploadFile | None = File(default=None),
    image_style: str = Form(default="ghibli_animation"),
    name: str | None = Form(default=None),
    age: int | None = Form(default=None),
    gender: str | None = Form(default=None),
    fitness_goal: str | None = Form(default=None),
    height: str | None = Form(default=None),
    weight: float | None = Form(default=None),
    target_weight: float | None = Form(default=None),
    bio: str | None = Form(default=None),
    fitness_motivation: str | None = Form(default=None),
    current_user: User = Depends(get_current_coach),
    storybook_service: StorybookService = Depends(get_storybook_service),
) -> StorybookGenerateResponse:
    try:
        job = await storybook_service.create_storybook_generation(
            current_coach=current_user,
            client_id=_parse_uuid(client_id),
            selfie=selfie,
            wake_up_time=wake_up_time,
            bed_time=bed_time,
            image_style=image_style,
            name=name,
            age=age,
            gender=gender,
            fitness_goal=fitness_goal,
            height=height,
            weight=weight,
            target_weight=target_weight,
            bio=bio,
            fitness_motivation=fitness_motivation,
        )
        if isinstance(storybook_service, StorybookService):
            background_tasks.add_task(_run_storybook_generation, job)
        return StorybookGenerateResponse(storybook_id=job.storybook_id)
    except StorybookAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except StorybookValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get(
    "/storybook",
    response_model=list[StorybookRead],
    summary="Get latest storybook(s)",
)
def get_latest_storybooks(
    current_user: User = Depends(get_current_onboarded_user),
    storybook_service: StorybookService = Depends(get_storybook_service),
) -> list[StorybookRead]:
    latest = storybook_service.get_latest_storybooks(current_user=current_user)
    payload: list[StorybookRead] = []
    for storybook, pages in latest:
        item = StorybookRead.model_validate(storybook)
        item.pages = [StoryPageRead.model_validate(page) for page in pages]
        payload.append(item)
    return payload


@router.get(
    "/storybook/coach/clients/status",
    response_model=list[CoachClientStorybookStatusRead],
    summary="Get all assigned clients storybook validity status",
)
def get_coach_clients_storybook_status(
    current_user: User = Depends(get_current_coach),
    storybook_service: StorybookService = Depends(get_storybook_service),
) -> list[CoachClientStorybookStatusRead]:
    try:
        return storybook_service.get_coach_client_storybook_statuses(current_coach=current_user)
    except StorybookAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/storybook/{storybook_id}",
    response_model=StorybookRead,
    summary="Get storybook by id",
)
def get_storybook(
    storybook_id: str,
    current_user: User = Depends(get_current_onboarded_user),
    storybook_service: StorybookService = Depends(get_storybook_service),
) -> StorybookRead:
    try:
        storybook, pages = storybook_service.get_storybook(
            current_user=current_user,
            storybook_id=_parse_uuid(storybook_id),
        )
    except StorybookNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorybookAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    payload = StorybookRead.model_validate(storybook)
    payload.pages = [StoryPageRead.model_validate(page) for page in pages]
    return payload


@router.get(
    "/storybook/{storybook_id}/page/{page_number}",
    response_model=StoryPageRead,
    summary="Get storybook page",
)
def get_storybook_page(
    storybook_id: str,
    page_number: int,
    current_user: User = Depends(get_current_onboarded_user),
    storybook_service: StorybookService = Depends(get_storybook_service),
) -> StoryPageRead:
    try:
        page = storybook_service.get_storybook_page(
            current_user=current_user,
            storybook_id=_parse_uuid(storybook_id),
            page_number=page_number,
        )
    except StorybookNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StoryPageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorybookAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return StoryPageRead.model_validate(page)


@router.post(
    "/storybook/generate/execute",
    response_model=StorybookGenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute storybook generation from provided context",
)
async def execute_storybook_generation_from_context(
    background_tasks: BackgroundTasks,
    client_id: str = Form(...),
    context_json: str | None = Form(default=None),
    selfie: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_coach),
    storybook_service: StorybookService = Depends(get_storybook_service),
) -> StorybookGenerateResponse:
    try:
        context_override = _normalize_context_override(context_json)
        job = await storybook_service.create_storybook_generation(
            current_coach=current_user,
            client_id=_parse_uuid(client_id),
            selfie=selfie,
            wake_up_time=None,
            bed_time=None,
            image_style=None,
            name=None,
            age=None,
            gender=None,
            fitness_goal=None,
            height=None,
            weight=None,
            target_weight=None,
            bio=None,
            fitness_motivation=None,
        )
        if context_override is not None:
            job = replace(job, context_json=context_override)
        if isinstance(storybook_service, StorybookService):
            background_tasks.add_task(_run_storybook_generation, job)
        return StorybookGenerateResponse(storybook_id=job.storybook_id)
    except StorybookAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except StorybookValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get(
    "/storybook/{storybook_id}/status",
    response_model=StorybookStatusResponse,
    summary="Get storybook generation status",
)
def get_storybook_status(
    storybook_id: str,
    current_user: User = Depends(get_current_onboarded_user),
    storybook_service: StorybookService = Depends(get_storybook_service),
) -> StorybookStatusResponse:
    try:
        status_value = storybook_service.get_storybook_status(
            current_user=current_user,
            storybook_id=_parse_uuid(storybook_id),
        )
    except StorybookNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorybookAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return StorybookStatusResponse(storybook_id=_parse_uuid(storybook_id), status=status_value)


@router.put(
    "/storybook/{storybook_id}/page/{page_number}",
    response_model=StoryPageRead,
    summary="Edit storybook page text",
)
def update_storybook_page(
    storybook_id: str,
    page_number: int,
    payload: StoryPageUpdateRequest,
    current_user: User = Depends(get_current_onboarded_user),
    storybook_service: StorybookService = Depends(get_storybook_service),
) -> StoryPageRead:
    try:
        page = storybook_service.update_story_page(
            current_user=current_user,
            storybook_id=_parse_uuid(storybook_id),
            page_number=page_number,
            story=payload.story,
        )
    except StorybookNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StoryPageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorybookAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return StoryPageRead.model_validate(page)


@router.post(
    "/storybook/{storybook_id}/page/{page_number}/regenerate-story",
    response_model=StoryPageRead,
    summary="Regenerate story text",
)
async def regenerate_storybook_page_story(
    storybook_id: str,
    page_number: int,
    payload: RegeneratePageRequest | None = None,
    current_user: User = Depends(get_current_onboarded_user),
    storybook_service: StorybookService = Depends(get_storybook_service),
) -> StoryPageRead:
    try:
        page = await storybook_service.regenerate_story(
            current_user=current_user,
            storybook_id=_parse_uuid(storybook_id),
            page_number=page_number,
            payload=payload,
        )
    except (AIServiceError, AIServiceResponseError) as exc:
        raise _map_ai_exception(exc) from exc
    except StorybookNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StoryPageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorybookAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return StoryPageRead.model_validate(page)


@router.post(
    "/storybook/{storybook_id}/page/{page_number}/regenerate-image",
    response_model=StoryPageRead,
    summary="Regenerate storybook image",
)
async def regenerate_storybook_page_image(
    storybook_id: str,
    page_number: int,
    payload: RegenerateImageRequest | None = None,
    current_user: User = Depends(get_current_onboarded_user),
    storybook_service: StorybookService = Depends(get_storybook_service),
) -> StoryPageRead:
    try:
        page = await storybook_service.regenerate_image(
            current_user=current_user,
            storybook_id=_parse_uuid(storybook_id),
            page_number=page_number,
            payload=payload,
        )
    except (AIServiceError, AIServiceResponseError) as exc:
        raise _map_ai_exception(exc) from exc
    except StorybookNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StoryPageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorybookAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return StoryPageRead.model_validate(page)


@router.post(
    "/storybook/{storybook_id}/page/{page_number}/regenerate",
    response_model=StoryPageRead,
    summary="Regenerate story and image",
)
async def regenerate_storybook_page(
    storybook_id: str,
    page_number: int,
    payload: RegeneratePageRequest | None = None,
    current_user: User = Depends(get_current_onboarded_user),
    storybook_service: StorybookService = Depends(get_storybook_service),
) -> StoryPageRead:
    try:
        page = await storybook_service.regenerate_story_and_image(
            current_user=current_user,
            storybook_id=_parse_uuid(storybook_id),
            page_number=page_number,
            payload=payload,
        )
    except (AIServiceError, AIServiceResponseError) as exc:
        raise _map_ai_exception(exc) from exc
    except StorybookNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StoryPageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorybookAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return StoryPageRead.model_validate(page)


@router.get(
    "/storybook/{storybook_id}/pdf",
    response_model=StorybookPdfResponse,
    summary="Get storybook PDF url",
)
def get_storybook_pdf(
    storybook_id: str,
    current_user: User = Depends(get_current_onboarded_user),
    storybook_service: StorybookService = Depends(get_storybook_service),
) -> StorybookPdfResponse:
    try:
        pdf_url = storybook_service.get_pdf_url(
            current_user=current_user,
            storybook_id=_parse_uuid(storybook_id),
        )
    except StorybookNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorybookAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return StorybookPdfResponse(pdf_url=pdf_url)


def _parse_uuid(value: str):
    try:
        from uuid import UUID

        return UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid storybook id",
        ) from exc


async def _run_storybook_generation(job: StorybookGenerationJob) -> None:
    db = SessionLocal()
    try:
        service = StorybookService(
            db=db,
            ai_service=AIService(),
            storybook_repository=StorybookRepository(db),
            story_page_repository=StoryPageRepository(db),
            routine_repository=RoutineRepository(db),
            nutrition_plan_repository=NutritionPlanRepository(db),
            user_repository=UserRepository(db),
            coach_client_repository=CoachClientRepository(db),
        )
        await service.process_storybook_generation(job=job)
    finally:
        db.close()


def _normalize_context_override(context_json: str | None) -> str | None:
    if context_json is None:
        return None

    normalized = context_json.strip()
    if normalized == "" or normalized.lower() in {"null", "string"}:
        return None

    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise StorybookValidationError(
            "context_json must be a valid JSON object, or leave it empty for automatic context"
        ) from exc

    if not isinstance(parsed, dict):
        raise StorybookValidationError(
            "context_json must be a JSON object, or leave it empty for automatic context"
        )

    return json.dumps(parsed, separators=(",", ":"))