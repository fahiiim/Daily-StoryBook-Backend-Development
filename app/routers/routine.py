from datetime import date as dt_date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies.auth import get_current_onboarded_user
from app.dependencies.routine import get_routine_service
from app.models.routine_macro_log import MacroType, RoutineMacroLog
from app.models.routine import Routine
from app.models.user import User
from app.schemas.routine import (
    RoutineCreate,
    RoutineMacroLogCreate,
    RoutineMacroLogCreateResponse,
    RoutineMacroLogRead,
    RoutinePatch,
    RoutinePut,
    RoutineRead,
    RoutineRecentFoodRead,
)
from app.services.routine_service import (
    EmptyRoutineUpdateError,
    RoutineAlreadyExistsError,
    RoutineNotFoundError,
    RoutineService,
)

router = APIRouter(tags=["routines"])


@router.get(
    "/routines/today",
    response_model=RoutineRead,
    summary="Get or initialize today's routine",
)
def get_today_routine(
    routine_date: dt_date | None = Query(default=None),
    current_user: User = Depends(get_current_onboarded_user),
    routine_service: RoutineService = Depends(get_routine_service),
) -> Routine:
    target_date = routine_date or dt_date.today()
    return routine_service.get_or_create_routine_for_date(
        current_user=current_user,
        target_date=target_date,
    )


@router.post(
    "/routines",
    response_model=RoutineRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create daily routine",
)
def create_routine(
    payload: RoutineCreate,
    current_user: User = Depends(get_current_onboarded_user),
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
    current_user: User = Depends(get_current_onboarded_user),
    routine_service: RoutineService = Depends(get_routine_service),
) -> list[Routine]:
    return routine_service.list_routines(current_user=current_user)


@router.get(
    "/routines/macro-recent",
    response_model=list[RoutineRecentFoodRead],
    summary="List recent foods for a macro type",
)
def list_recent_macro_foods(
    macro_type: MacroType = Query(...),
    limit: int = Query(default=8, ge=1, le=50),
    current_user: User = Depends(get_current_onboarded_user),
    routine_service: RoutineService = Depends(get_routine_service),
) -> list[RoutineRecentFoodRead]:
    recent = routine_service.list_recent_macro_foods(
        current_user=current_user,
        macro_type=macro_type,
        limit=limit,
    )
    return [
        RoutineRecentFoodRead(
            macro_type=item.macro_type,
            food_name=item.food_name,
            amount=item.amount,
            amount_unit=item.amount_unit,
            macro_grams=item.macro_grams,
            kcal=item.kcal,
            last_logged_at=item.last_logged_at,
        )
        for item in recent
    ]


@router.get(
    "/routines/{routine_id}",
    response_model=RoutineRead,
    summary="Get routine by id",
)
def get_routine(
    routine_id: UUID,
    current_user: User = Depends(get_current_onboarded_user),
    routine_service: RoutineService = Depends(get_routine_service),
) -> Routine:
    try:
        return routine_service.get_routine(current_user=current_user, routine_id=routine_id)
    except RoutineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/routines/{routine_id}/macro-logs",
    response_model=list[RoutineMacroLogRead],
    summary="List logged meals or macro entries for a routine",
)
def list_macro_logs(
    routine_id: UUID,
    current_user: User = Depends(get_current_onboarded_user),
    routine_service: RoutineService = Depends(get_routine_service),
) -> list[RoutineMacroLog]:
    try:
        return routine_service.list_macro_logs(current_user=current_user, routine_id=routine_id)
    except RoutineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/routines/{routine_id}/macro-logs",
    response_model=RoutineMacroLogCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a macro food entry to daily log",
)
def add_macro_log(
    routine_id: UUID,
    payload: RoutineMacroLogCreate,
    current_user: User = Depends(get_current_onboarded_user),
    routine_service: RoutineService = Depends(get_routine_service),
) -> RoutineMacroLogCreateResponse:
    try:
        routine, log = routine_service.add_macro_log(
            current_user=current_user,
            routine_id=routine_id,
            payload=payload,
        )
    except RoutineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return RoutineMacroLogCreateResponse(
        routine=RoutineRead.model_validate(routine),
        log=RoutineMacroLogRead.model_validate(log),
    )


@router.put(
    "/routines/{routine_id}",
    response_model=RoutineRead,
    summary="Replace routine by id",
)
def put_routine(
    routine_id: UUID,
    payload: RoutinePut,
    current_user: User = Depends(get_current_onboarded_user),
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
    current_user: User = Depends(get_current_onboarded_user),
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
    current_user: User = Depends(get_current_onboarded_user),
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