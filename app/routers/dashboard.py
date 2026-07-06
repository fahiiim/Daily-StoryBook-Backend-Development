from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_coach
from app.dependencies.dashboard import get_dashboard_service
from app.models.user import User
from app.schemas.dashboard import CoachDashboardResponse, DashboardResponse
from app.services.dashboard_service import DashboardAccessError, DashboardNotFoundError, DashboardService

router = APIRouter(tags=["dashboard"])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get coach dashboard or client dashboard",
)
def get_dashboard(
    client_id: UUID | None = Query(default=None),
    current_coach: User = Depends(get_current_coach),
    dashboard_service: DashboardService = Depends(get_dashboard_service),
) -> DashboardResponse:
    try:
        if client_id is None:
            coach_dashboard = dashboard_service.get_coach_dashboard(current_coach=current_coach)
            return DashboardResponse(coach_dashboard=coach_dashboard)

        client_dashboard = dashboard_service.get_client_dashboard(
            current_coach=current_coach,
            client_id=client_id,
        )
        return DashboardResponse(client_dashboard=client_dashboard)
    except DashboardAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except DashboardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/coach/dashboard",
    response_model=CoachDashboardResponse,
    summary="Get coach dashboard",
)
def get_coach_dashboard(
    current_coach: User = Depends(get_current_coach),
    dashboard_service: DashboardService = Depends(get_dashboard_service),
) -> CoachDashboardResponse:
    try:
        return dashboard_service.get_coach_dashboard(current_coach=current_coach)
    except DashboardAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
