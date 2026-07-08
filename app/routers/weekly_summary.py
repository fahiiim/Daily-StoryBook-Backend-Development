from datetime import date as dt_date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_onboarded_user
from app.dependencies.weekly_summary import get_weekly_summary_service
from app.models.user import User
from app.schemas.weekly_summary import (
    WeeklySummaryGenerateResponse,
    WeeklySummaryHistoryResponse,
    WeeklySummaryRead,
)
from app.services.ai_service import (
    AIServiceConfigError,
    AIServiceConnectionError,
    AIServiceError,
    AIServiceResponseError,
    AIServiceTimeoutError,
)
from app.services.weekly_summary_service import (
    WeeklySummaryAccessError,
    WeeklySummaryNotFoundError,
    WeeklySummaryService,
    WeeklySummaryValidationError,
)

router = APIRouter(tags=["weekly-summary"])


@router.get(
    "/weekly-summary",
    summary="Get weekly summary (legacy compatibility)",
)
def get_weekly_summary_legacy(
    week_start: dt_date | None = Query(default=None),
    current_user: User = Depends(get_current_onboarded_user),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> dict[str, object]:
    legacy_method = getattr(weekly_summary_service, "get_weekly_summary", None)
    if callable(legacy_method):
        payload = legacy_method(current_user=current_user, week_start=week_start)
        if isinstance(payload, dict):
            return payload

    try:
        summary = weekly_summary_service.get_current_summary(
            current_user=current_user,
            user_id=None,
        )
    except WeeklySummaryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklySummaryAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return {
        "week_start": str(summary.week_start),
        "week_end": str(summary.week_end),
        "summary": summary.summary,
        "image_url": summary.image_url,
        "generated_at": summary.generated_at.isoformat(),
    }


@router.post(
    "/weekly-summary/generate",
    response_model=WeeklySummaryGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate weekly summary",
)
async def generate_weekly_summary(
    user_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_onboarded_user),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> WeeklySummaryGenerateResponse:
    try:
        summary = await weekly_summary_service.generate_weekly_summary(
            current_user=current_user,
            user_id=user_id,
        )
    except WeeklySummaryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except WeeklySummaryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklySummaryAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except (AIServiceError, AIServiceResponseError) as exc:
        raise _map_ai_exception(exc) from exc

    return WeeklySummaryGenerateResponse(summary=WeeklySummaryRead.model_validate(summary))


@router.get(
    "/weekly-summary/current",
    response_model=WeeklySummaryRead,
    summary="Get current weekly summary",
)
def get_current_weekly_summary(
    user_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_onboarded_user),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> WeeklySummaryRead:
    try:
        summary = weekly_summary_service.get_current_summary(
            current_user=current_user,
            user_id=user_id,
        )
    except WeeklySummaryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklySummaryAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return WeeklySummaryRead.model_validate(summary)


@router.get(
    "/weekly-summary/history",
    response_model=WeeklySummaryHistoryResponse,
    summary="Get weekly summary history",
)
def get_weekly_summary_history(
    user_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_onboarded_user),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> WeeklySummaryHistoryResponse:
    try:
        summaries = weekly_summary_service.get_history(
            current_user=current_user,
            user_id=user_id,
        )
    except WeeklySummaryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklySummaryAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return WeeklySummaryHistoryResponse(
        summaries=[WeeklySummaryRead.model_validate(summary) for summary in summaries],
    )


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