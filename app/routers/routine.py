from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.dependencies.auth import get_current_user
from app.dependencies.routine import get_routine_service
from app.models.routine import Routine
from app.models.user import User
from app.schemas.routine import RoutineCreate, RoutinePatch, RoutinePut, RoutineRead
from app.services.routine_service import (
    EmptyRoutineUpdateError,
    RoutineAlreadyExistsError,
    RoutineNotFoundError,
    RoutineService,
)

router = APIRouter(tags=["routines"])


@router.post(
    "/routines",
    response_model=RoutineRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create daily routine",
)
def create_routine(
    payload: RoutineCreate,
    current_user: User = Depends(get_current_user),
    routine_service: RoutineService = Depends(get_routine_service),
) -> Routine:
    try:
        return routine_service.create_routine(current_user=current_user, payload=payload)
    except RoutineAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/routines",
    response_model=list[RoutineRead],
    summary="List routines for current user",
)
def list_routines(
    current_user: User = Depends(get_current_user),
    routine_service: RoutineService = Depends(get_routine_service),
) -> list[Routine]:
    return routine_service.list_routines(current_user=current_user)


@router.get(
    "/routines/{routine_id}",
    response_model=RoutineRead,
    summary="Get routine by id",
)
def get_routine(
    routine_id: UUID,
    current_user: User = Depends(get_current_user),
    routine_service: RoutineService = Depends(get_routine_service),
) -> Routine:
    try:
        return routine_service.get_routine(current_user=current_user, routine_id=routine_id)
    except RoutineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.put(
    "/routines/{routine_id}",
    response_model=RoutineRead,
    summary="Replace routine by id",
)
def put_routine(
    routine_id: UUID,
    payload: RoutinePut,
    current_user: User = Depends(get_current_user),
    routine_service: RoutineService = Depends(get_routine_service),
) -> Routine:
    try:
        return routine_service.replace_routine(
            current_user=current_user,
            routine_id=routine_id,
            payload=payload,
        )
    except RoutineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RoutineAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.patch(
    "/routines/{routine_id}",
    response_model=RoutineRead,
    summary="Partially update routine by id",
)
def patch_routine(
    routine_id: UUID,
    payload: RoutinePatch,
    current_user: User = Depends(get_current_user),
    routine_service: RoutineService = Depends(get_routine_service),
) -> Routine:
    try:
        return routine_service.patch_routine(
            current_user=current_user,
            routine_id=routine_id,
            payload=payload,
        )
    except RoutineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RoutineAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except EmptyRoutineUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/routines/{routine_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete routine by id",
)
def delete_routine(
    routine_id: UUID,
    current_user: User = Depends(get_current_user),
    routine_service: RoutineService = Depends(get_routine_service),
) -> Response:
    try:
        routine_service.delete_routine(current_user=current_user, routine_id=routine_id)
    except RoutineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)