from datetime import date as dt_date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies.auth import get_current_coach, get_current_self
from app.dependencies.routine import get_routine_service
from app.models.nutrition_plan import NutritionPlan
from app.models.routine import Routine
from app.models.routine_macro_log import MacroType, RoutineMacroLog
from app.models.user import User
from app.schemas.nutrition_plan import NutritionPlanRead
from app.schemas.routine import (
    RoutineCreate,
    RoutineDashboardRead,
    RoutineMacroLogCreate,
    RoutineMacroLogCreateResponse,
    RoutineMacroLogRead,
    RoutineMacroLogUpdate,
    RoutineMacroRemainingRead,
    RoutineMacroTotalsRead,
    RoutinePatch,
    RoutinePut,
    RoutineRead,
    RoutineRecentFoodRead,
)
from app.services.routine_service import (
    EmptyRoutineUpdateError,
    RoutineAlreadyExistsError,
    RoutineClientNotFoundError,
    RoutineClientNotManagedError,
    RoutineMacroLogNotFoundError,
    RoutineNotFoundError,
    RoutineService,
)

router = APIRouter(tags=["routines"])


def _routine_read(routine: Routine, nutrition_plan: NutritionPlan | None) -> RoutineRead:
    routine_read = RoutineRead.model_validate(routine)
    nutrition_plan_read = (
        NutritionPlanRead.model_validate(nutrition_plan) if nutrition_plan else None
    )
    return routine_read.model_copy(
        update={
            "nutrition_plan": nutrition_plan_read,
            "goal_kcal": (
                float(nutrition_plan.daily_calories)
                if nutrition_plan is not None and nutrition_plan.daily_calories is not None
                else None
            ),
            "goal_protein": (
                float(nutrition_plan.protein)
                if nutrition_plan is not None and nutrition_plan.protein is not None
                else None
            ),
            "goal_carbs": (
                float(nutrition_plan.carbs)
                if nutrition_plan is not None and nutrition_plan.carbs is not None
                else None
            ),
            "goal_fats": (
                float(nutrition_plan.fat)
                if nutrition_plan is not None and nutrition_plan.fat is not None
                else None
            ),
            "goal_fiber": (
                float(nutrition_plan.fiber)
                if nutrition_plan is not None and nutrition_plan.fiber is not None
                else None
            ),
        }
    )


def _build_dashboard(
    *,
    target_date: dt_date,
    routine: Routine | None,
    nutrition_plan: NutritionPlan | None,
    logs: list[RoutineMacroLog],
) -> RoutineDashboardRead:
    consumed_kcal = round(sum(log.kcal for log in logs), 2)
    consumed_protein = round(sum(log.protein for log in logs), 2)
    consumed_carbs = round(sum(log.carbs for log in logs), 2)
    consumed_fat = round(sum(log.fat for log in logs), 2)
    consumed_fiber = round(sum(log.fiber for log in logs), 2)
    consumed_water = round(routine.water_intake or 0.0, 2) if routine is not None else 0.0

    def remaining(target: float | int | None, consumed: float) -> float | None:
        return None if target is None else round(float(target) - consumed, 2)

    return RoutineDashboardRead(
        date=target_date,
        routine=_routine_read(routine, nutrition_plan) if routine is not None else None,
        nutrition_plan=nutrition_plan,
        totals=RoutineMacroTotalsRead(
            kcal=consumed_kcal,
            protein=consumed_protein,
            carbs=consumed_carbs,
            fat=consumed_fat,
            fiber=consumed_fiber,
            water=consumed_water,
        ),
        remaining=RoutineMacroRemainingRead(
            kcal=(
                remaining(nutrition_plan.daily_calories, consumed_kcal)
                if nutrition_plan
                else None
            ),
            protein=remaining(nutrition_plan.protein, consumed_protein) if nutrition_plan else None,
            carbs=remaining(nutrition_plan.carbs, consumed_carbs) if nutrition_plan else None,
            fat=remaining(nutrition_plan.fat, consumed_fat) if nutrition_plan else None,
            fiber=remaining(nutrition_plan.fiber, consumed_fiber) if nutrition_plan else None,
            water=remaining(nutrition_plan.water_goal, consumed_water) if nutrition_plan else None,
        ),
        logged_meals=[RoutineMacroLogRead.model_validate(log) for log in logs],
    )


@router.get(
    "/routines/today",
    response_model=RoutineRead,
    summary="Get or initialize today's client tracking record",
)
def get_today_routine(
    routine_date: dt_date | None = Query(default=None),
    current_user: User = Depends(get_current_self),
    routine_service: RoutineService = Depends(get_routine_service),
) -> RoutineRead:
    target_date = routine_date or dt_date.today()
    routine = routine_service.get_or_create_routine_for_date(
        current_user=current_user,
        target_date=target_date,
    )
    nutrition_plan = routine_service.get_nutrition_plan_for_date(
        client_id=current_user.id,
        routine_date=target_date,
    )
    return _routine_read(routine, nutrition_plan)


@router.get(
    "/routines/today/dashboard",
    response_model=RoutineDashboardRead,
    summary="Get today's nutrition-linked routine dashboard",
)
def get_today_routine_dashboard(
    routine_date: dt_date | None = Query(default=None),
    current_user: User = Depends(get_current_self),
    routine_service: RoutineService = Depends(get_routine_service),
) -> RoutineDashboardRead:
    target_date = routine_date or dt_date.today()
    routine = routine_service.get_routine_for_date(
        current_user=current_user,
        target_date=target_date,
    )
    nutrition_plan = routine_service.get_nutrition_plan_for_date(
        client_id=current_user.id,
        routine_date=target_date,
    )
    logged_meals = (
        routine_service.list_macro_logs(current_user=current_user, routine_id=routine.id)
        if routine is not None
        else []
    )
    return _build_dashboard(
        target_date=target_date,
        routine=routine,
        nutrition_plan=nutrition_plan,
        logs=logged_meals,
    )


@router.post(
    "/routines",
    response_model=RoutineRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create daily routine",
)
def create_routine(
    payload: RoutineCreate,
    current_user: User = Depends(get_current_self),
    routine_service: RoutineService = Depends(get_routine_service),
) -> RoutineRead:
    try:
        routine = routine_service.create_routine(current_user=current_user, payload=payload)
    except RoutineAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    nutrition_plan = routine_service.get_nutrition_plan_for_date(
        client_id=current_user.id,
        routine_date=routine.date,
    )
    return _routine_read(routine, nutrition_plan)


@router.get(
    "/routines",
    response_model=list[RoutineRead],
    summary="List routines for current user",
)
def list_routines(
    current_user: User = Depends(get_current_self),
    routine_service: RoutineService = Depends(get_routine_service),
) -> list[RoutineRead]:
    routines = routine_service.list_routines(current_user=current_user)
    return [
        _routine_read(
            routine,
            routine_service.get_nutrition_plan_for_date(
                client_id=current_user.id,
                routine_date=routine.date,
            ),
        )
        for routine in routines
    ]


@router.get(
    "/routines/macro-recent",
    response_model=list[RoutineRecentFoodRead],
    summary="List recent foods for a macro type",
)
def list_recent_macro_foods(
    macro_type: MacroType = Query(...),
    limit: int = Query(default=8, ge=1, le=50),
    current_user: User = Depends(get_current_self),
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
            kcal=item.kcal,
            protein=item.protein,
            carbs=item.carbs,
            fat=item.fat,
            fiber=item.fiber,
            last_logged_at=item.last_logged_at,
        )
        for item in recent
    ]


@router.post(
    "/routines/today/macro-logs",
    response_model=RoutineMacroLogCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a complete meal to today's client log",
)
def add_today_macro_log(
    payload: RoutineMacroLogCreate,
    routine_date: dt_date | None = Query(default=None),
    current_user: User = Depends(get_current_self),
    routine_service: RoutineService = Depends(get_routine_service),
) -> RoutineMacroLogCreateResponse:
    target_date = routine_date or dt_date.today()
    routine = routine_service.get_or_create_routine_for_date(
        current_user=current_user,
        target_date=target_date,
    )
    updated_routine, log = routine_service.add_macro_log(
        current_user=current_user,
        routine_id=routine.id,
        payload=payload,
    )
    nutrition_plan = routine_service.get_nutrition_plan_for_date(
        client_id=current_user.id,
        routine_date=target_date,
    )

    return RoutineMacroLogCreateResponse(
        routine=_routine_read(updated_routine, nutrition_plan),
        log=RoutineMacroLogRead.model_validate(log),
    )


@router.get(
    "/coach/clients/{client_id}/routines/today/dashboard",
    response_model=RoutineDashboardRead,
    summary="View managed client's nutrition-linked routine dashboard",
)
def get_client_today_routine_dashboard(
    client_id: UUID,
    routine_date: dt_date | None = Query(default=None),
    current_coach: User = Depends(get_current_coach),
    routine_service: RoutineService = Depends(get_routine_service),
) -> RoutineDashboardRead:
    target_date = routine_date or dt_date.today()
    try:
        routine = routine_service.get_client_routine_for_date(
            current_coach=current_coach,
            client_id=client_id,
            target_date=target_date,
        )
        nutrition_plan = routine_service.get_nutrition_plan_for_date(
            client_id=client_id,
            routine_date=target_date,
            coach_id=current_coach.id,
        )
        logged_meals = (
            routine_service.list_client_macro_logs(
                current_coach=current_coach,
                client_id=client_id,
                routine_id=routine.id,
            )
            if routine is not None
            else []
        )
    except RoutineClientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoutineClientNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return _build_dashboard(
        target_date=target_date,
        routine=routine,
        nutrition_plan=nutrition_plan,
        logs=logged_meals,
    )


@router.get(
    "/routines/{routine_id}",
    response_model=RoutineRead,
    summary="Get routine by id",
)
def get_routine(
    routine_id: UUID,
    current_user: User = Depends(get_current_self),
    routine_service: RoutineService = Depends(get_routine_service),
) -> RoutineRead:
    try:
        routine = routine_service.get_routine(current_user=current_user, routine_id=routine_id)
    except RoutineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    nutrition_plan = routine_service.get_nutrition_plan_for_date(
        client_id=current_user.id,
        routine_date=routine.date,
    )
    return _routine_read(routine, nutrition_plan)


@router.get(
    "/routines/{routine_id}/macro-logs",
    response_model=list[RoutineMacroLogRead],
    summary="List complete logged meals for a routine",
)
def list_macro_logs(
    routine_id: UUID,
    current_user: User = Depends(get_current_self),
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
    summary="Add a complete meal to the client daily log",
)
def add_macro_log(
    routine_id: UUID,
    payload: RoutineMacroLogCreate,
    current_user: User = Depends(get_current_self),
    routine_service: RoutineService = Depends(get_routine_service),
) -> RoutineMacroLogCreateResponse:
    try:
        routine, log = routine_service.add_macro_log(
            current_user=current_user,
            routine_id=routine_id,
            payload=payload,
        )
        nutrition_plan = routine_service.get_nutrition_plan_for_date(
            client_id=current_user.id,
            routine_date=routine.date,
        )
    except RoutineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return RoutineMacroLogCreateResponse(
        routine=_routine_read(routine, nutrition_plan),
        log=RoutineMacroLogRead.model_validate(log),
    )


@router.patch(
    "/routines/{routine_id}/macro-logs/{log_id}",
    response_model=RoutineMacroLogCreateResponse,
    summary="Update a logged meal and recalculate routine totals",
)
def patch_macro_log(
    routine_id: UUID,
    log_id: UUID,
    payload: RoutineMacroLogUpdate,
    current_user: User = Depends(get_current_self),
    routine_service: RoutineService = Depends(get_routine_service),
) -> RoutineMacroLogCreateResponse:
    try:
        routine, log = routine_service.update_macro_log(
            current_user=current_user,
            routine_id=routine_id,
            log_id=log_id,
            payload=payload,
        )
    except RoutineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoutineMacroLogNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    nutrition_plan = routine_service.get_nutrition_plan_for_date(
        client_id=current_user.id,
        routine_date=routine.date,
    )
    return RoutineMacroLogCreateResponse(
        routine=_routine_read(routine, nutrition_plan),
        log=RoutineMacroLogRead.model_validate(log),
    )


@router.delete(
    "/routines/{routine_id}/macro-logs/{log_id}",
    response_model=RoutineRead,
    summary="Delete a logged meal and recalculate routine totals",
)
def delete_macro_log(
    routine_id: UUID,
    log_id: UUID,
    current_user: User = Depends(get_current_self),
    routine_service: RoutineService = Depends(get_routine_service),
) -> RoutineRead:
    try:
        routine = routine_service.delete_macro_log(
            current_user=current_user,
            routine_id=routine_id,
            log_id=log_id,
        )
    except RoutineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoutineMacroLogNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    nutrition_plan = routine_service.get_nutrition_plan_for_date(
        client_id=current_user.id,
        routine_date=routine.date,
    )
    return _routine_read(routine, nutrition_plan)


@router.put(
    "/routines/{routine_id}",
    response_model=RoutineRead,
    summary="Replace routine by id",
)
def put_routine(
    routine_id: UUID,
    payload: RoutinePut,
    current_user: User = Depends(get_current_self),
    routine_service: RoutineService = Depends(get_routine_service),
) -> RoutineRead:
    try:
        routine = routine_service.replace_routine(
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
    nutrition_plan = routine_service.get_nutrition_plan_for_date(
        client_id=current_user.id,
        routine_date=routine.date,
    )
    return _routine_read(routine, nutrition_plan)


@router.patch(
    "/routines/{routine_id}",
    response_model=RoutineRead,
    summary="Partially update routine by id",
)
def patch_routine(
    routine_id: UUID,
    payload: RoutinePatch,
    current_user: User = Depends(get_current_self),
    routine_service: RoutineService = Depends(get_routine_service),
) -> RoutineRead:
    try:
        routine = routine_service.patch_routine(
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
    nutrition_plan = routine_service.get_nutrition_plan_for_date(
        client_id=current_user.id,
        routine_date=routine.date,
    )
    return _routine_read(routine, nutrition_plan)


@router.delete(
    "/routines/{routine_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete routine by id",
)
def delete_routine(
    routine_id: UUID,
    current_user: User = Depends(get_current_self),
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