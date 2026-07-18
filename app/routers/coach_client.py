from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.dependencies.auth import get_current_coach, get_current_user
from app.dependencies.coach_client import get_coach_client_service
from app.models.coach_client import CoachClient
from app.models.user import User
from app.schemas.coach_client import AddCoachClientRequest, CoachClientRead
from app.schemas.profile import ProfileRead
from app.services.coach_client_service import (
    CoachClientNotFoundError,
    CoachClientRequestNotFoundError,
    CoachClientRelationshipExistsError,
    CoachClientRelationshipNotFoundError,
    CoachClientService,
    InvalidCoachClientAssignmentError,
)

router = APIRouter(prefix="/coach", tags=["coach-client"])


@router.post(
    "/clients",
    response_model=CoachClientRead,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a client to current coach",
    responses={
        403: {"description": "Coach role required"},
        404: {"description": "Client not found"},
        409: {"description": "Duplicate pending request or coach-client relationship"},
    },
)
def add_client(
    payload: AddCoachClientRequest,
    current_coach: User = Depends(get_current_coach),
    coach_client_service: CoachClientService = Depends(get_coach_client_service),
) -> CoachClient:
    try:
        return coach_client_service.add_client(
            current_coach=current_coach,
            client_email=str(payload.client_email),
            personalized_message=payload.personalized_message,
            assign_initial_plan=payload.assign_initial_plan,
        )
    except InvalidCoachClientAssignmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except CoachClientRelationshipExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except CoachClientNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/client-requests",
    response_model=list[CoachClientRead],
    summary="List pending coach requests for current self user",
)
def list_client_requests(
    current_user: User = Depends(get_current_user),
    coach_client_service: CoachClientService = Depends(get_coach_client_service),
) -> list[CoachClient]:
    try:
        return coach_client_service.list_client_requests(current_user=current_user)
    except InvalidCoachClientAssignmentError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post(
    "/client-requests/{request_id}/accept",
    response_model=CoachClientRead,
    summary="Accept a pending coach client request",
)
def accept_client_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    coach_client_service: CoachClientService = Depends(get_coach_client_service),
) -> CoachClient:
    try:
        return coach_client_service.accept_client_request(
            current_user=current_user,
            request_id=request_id,
        )
    except InvalidCoachClientAssignmentError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except CoachClientRequestNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/clients/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a client from current coach",
    responses={
        403: {"description": "Coach role required"},
        404: {"description": "Relationship not found"},
    },
)
def remove_client(
    client_id: UUID,
    current_coach: User = Depends(get_current_coach),
    coach_client_service: CoachClientService = Depends(get_coach_client_service),
) -> Response:
    try:
        coach_client_service.remove_client(current_coach=current_coach, client_id=client_id)
    except CoachClientRelationshipNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/clients",
    response_model=list[ProfileRead],
    summary="List clients managed by current coach",
    responses={403: {"description": "Coach role required"}},
)
def list_clients(
    current_coach: User = Depends(get_current_coach),
    coach_client_service: CoachClientService = Depends(get_coach_client_service),
) -> list[User]:
    return coach_client_service.list_clients(current_coach=current_coach)


@router.get(
    "/clients/{client_id}/profile",
    response_model=ProfileRead,
    summary="Get profile of a specific client managed by current coach",
    responses={
        403: {"description": "Coach role required"},
        404: {"description": "Relationship not found"},
    },
)
def get_client_profile(
    client_id: UUID,
    current_coach: User = Depends(get_current_coach),
    coach_client_service: CoachClientService = Depends(get_coach_client_service),
) -> User:
    try:
        return coach_client_service.get_client_profile(
            current_coach=current_coach,
            client_id=client_id,
        )
    except CoachClientRelationshipNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc