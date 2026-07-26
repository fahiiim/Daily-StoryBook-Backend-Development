from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_coach, get_current_self
from app.dependencies.weekly_summary import get_weekly_summary_service
from app.models.user import User
from app.schemas.weekly_summary import (
    WeeklyGoalsRead,
    WeeklyMealsRead,
    WeeklyProgressAnalyticsRead,
    WeeklyWorkoutsRead,
)
from app.services.weekly_summary_service import (
    WeeklySummaryClientNotFoundError,
    WeeklySummaryClientNotManagedError,
    WeeklySummaryService,
)

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


@router.get(
    "/weekly-summary/workouts",
    response_model=WeeklyWorkoutsRead,
    summary="Get current-week assigned workouts",
)
def get_weekly_workouts(
    current_user: User = Depends(get_current_self),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> WeeklyWorkoutsRead:
    return weekly_summary_service.get_current_week_workouts(current_user=current_user)


@router.get(
    "/weekly-summary/meals",
    response_model=WeeklyMealsRead,
    summary="Get current-week meals and target completion",
)
def get_weekly_meals(
    current_user: User = Depends(get_current_self),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> WeeklyMealsRead:
    return weekly_summary_service.get_current_week_meals(current_user=current_user)


@router.get(
    "/weekly-summary/goals",
    response_model=WeeklyGoalsRead,
    summary="Get current-week assigned goals and completion",
)
def get_weekly_goals(
    current_user: User = Depends(get_current_self),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> WeeklyGoalsRead:
    return weekly_summary_service.get_current_week_goals(current_user=current_user)


@router.get(
    "/coach/clients/{client_id}/weekly-summary",
    response_model=WeeklyProgressAnalyticsRead,
    summary="View managed client's current-week analytics",
)
def get_client_weekly_summary(
    client_id: UUID,
    current_coach: User = Depends(get_current_coach),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> WeeklyProgressAnalyticsRead:
    try:
        return weekly_summary_service.get_client_current_week_analytics(
            current_coach=current_coach,
            client_id=client_id,
        )
    except WeeklySummaryClientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklySummaryClientNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/coach/clients/{client_id}/weekly-summary/workouts",
    response_model=WeeklyWorkoutsRead,
    summary="View managed client's current-week workouts",
)
def get_client_weekly_workouts(
    client_id: UUID,
    current_coach: User = Depends(get_current_coach),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> WeeklyWorkoutsRead:
    try:
        return weekly_summary_service.get_client_current_week_workouts(
            current_coach=current_coach,
            client_id=client_id,
        )
    except WeeklySummaryClientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklySummaryClientNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/coach/clients/{client_id}/weekly-summary/meals",
    response_model=WeeklyMealsRead,
    summary="View managed client's current-week meals",
)
def get_client_weekly_meals(
    client_id: UUID,
    current_coach: User = Depends(get_current_coach),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> WeeklyMealsRead:
    try:
        return weekly_summary_service.get_client_current_week_meals(
            current_coach=current_coach,
            client_id=client_id,
        )
    except WeeklySummaryClientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklySummaryClientNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/coach/clients/{client_id}/weekly-summary/goals",
    response_model=WeeklyGoalsRead,
    summary="View managed client's current-week goals",
)
def get_client_weekly_goals(
    client_id: UUID,
    current_coach: User = Depends(get_current_coach),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> WeeklyGoalsRead:
    try:
        return weekly_summary_service.get_client_current_week_goals(
            current_coach=current_coach,
            client_id=client_id,
        )
    except WeeklySummaryClientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeeklySummaryClientNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
