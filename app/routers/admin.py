from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.admin import get_admin_service
from app.dependencies.auth import get_current_admin
from app.models.user import User, UserRole
from app.schemas.admin import (
    AdminDashboardResponse,
    AdminStorybookListResponse,
    AdminSubscriptionListResponse,
    AdminUserListResponse,
)
from app.schemas.user import UserRead
from app.services.admin_service import AdminAccessError, AdminNotFoundError, AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/dashboard",
    response_model=AdminDashboardResponse,
    summary="Get admin dashboard",
)
def get_admin_dashboard(
    current_admin: User = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> AdminDashboardResponse:
    try:
        return admin_service.get_dashboard(current_admin=current_admin)
    except AdminAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="List users",
)
def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="desc"),
    sort_field: str = Query(default="created_at"),
    search: str | None = Query(default=None),
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    current_admin: User = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> AdminUserListResponse:
    try:
        return admin_service.list_users(
            current_admin=current_admin,
            limit=limit,
            offset=offset,
            sort=sort,
            sort_field=sort_field,
            search=search,
            role=role,
            is_active=is_active,
        )
    except AdminAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/storybooks",
    response_model=AdminStorybookListResponse,
    summary="List storybooks",
)
def list_storybooks(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="desc"),
    user_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    current_admin: User = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> AdminStorybookListResponse:
    try:
        return admin_service.list_storybooks(
            current_admin=current_admin,
            limit=limit,
            offset=offset,
            sort=sort,
            user_id=user_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )
    except AdminAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/subscriptions",
    response_model=AdminSubscriptionListResponse,
    summary="List subscriptions",
)
def list_subscriptions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="desc"),
    user_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    current_admin: User = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> AdminSubscriptionListResponse:
    try:
        return admin_service.list_subscriptions(
            current_admin=current_admin,
            limit=limit,
            offset=offset,
            sort=sort,
            user_id=user_id,
            status=status,
        )
    except AdminAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.put(
    "/users/{user_id}/block",
    response_model=UserRead,
    summary="Block user",
)
def block_user(
    user_id: UUID,
    current_admin: User = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> UserRead:
    try:
        return admin_service.block_user(current_admin=current_admin, user_id=user_id)
    except AdminAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/users/{user_id}/activate",
    response_model=UserRead,
    summary="Activate user",
)
def activate_user(
    user_id: UUID,
    current_admin: User = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> UserRead:
    try:
        return admin_service.activate_user(current_admin=current_admin, user_id=user_id)
    except AdminAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete user",
)
def delete_user(
    user_id: UUID,
    current_admin: User = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> None:
    try:
        admin_service.soft_delete_user(current_admin=current_admin, user_id=user_id)
    except AdminAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
