from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user
from app.dependencies.notification import get_notification_service
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationRead,
    NotificationUnreadCountResponse,
)
from app.services.notification_service import (
    NotificationNotFoundError,
    NotificationService,
)

router = APIRouter(tags=["notifications"])


@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="List notifications",
)
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="desc"),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse:
    sort_desc = sort.lower() != "asc"
    items, total = notification_service.list_notifications(
        current_user=current_user,
        limit=limit,
        offset=offset,
        sort_desc=sort_desc,
    )
    return NotificationListResponse(
        items=[NotificationRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/notifications/unread-count",
    response_model=NotificationUnreadCountResponse,
    summary="Get unread notifications count",
)
def get_unread_count(
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> NotificationUnreadCountResponse:
    count = notification_service.unread_count(current_user=current_user)
    return NotificationUnreadCountResponse(unread_count=count)


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=NotificationRead,
    summary="Mark notification as read",
)
def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> NotificationRead:
    try:
        notification = notification_service.mark_read(
            current_user=current_user,
            notification_id=notification_id,
        )
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return NotificationRead.model_validate(notification)


@router.patch(
    "/notifications/read-all",
    summary="Mark all notifications as read",
)
def mark_all_read(
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> dict[str, int]:
    updated = notification_service.mark_all_read(current_user=current_user)
    return {"updated": updated}


@router.delete(
    "/notifications/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification",
)
def delete_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> None:
    try:
        notification_service.delete_notification(
            current_user=current_user,
            notification_id=notification_id,
        )
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
