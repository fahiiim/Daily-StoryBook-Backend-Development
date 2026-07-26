from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_self
from app.dependencies.weekly_summary import get_weekly_summary_service
from app.models.user import User
from app.schemas.weekly_summary import WeeklyProgressAnalyticsRead
from app.services.weekly_summary_service import WeeklySummaryService

router = APIRouter(tags=["weekly-summary"])


@router.get(
    "/weekly-summary",
    response_model=WeeklyProgressAnalyticsRead,
    summary="Get live current-week progress analytics",
)
def get_weekly_summary_analytics(
    current_user: User = Depends(get_current_self),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> WeeklyProgressAnalyticsRead:
    return weekly_summary_service.get_current_week_analytics(current_user=current_user)
