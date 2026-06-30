from datetime import date

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.dependencies.weekly_summary import get_weekly_summary_service
from app.models.user import User
from app.schemas.weekly_summary import WeeklySummaryResponse
from app.services.weekly_summary_service import WeeklySummaryService

router = APIRouter(tags=["weekly-summary"])


@router.get(
    "/weekly-summary",
    response_model=WeeklySummaryResponse,
    summary="Get weekly summary from routines",
)
def get_weekly_summary(
    week_start: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> WeeklySummaryResponse:
    return weekly_summary_service.get_weekly_summary(
        current_user=current_user,
        week_start=week_start,
    )