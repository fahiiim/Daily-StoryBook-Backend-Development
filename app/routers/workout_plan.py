from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.dependencies.auth import get_current_coach, get_current_onboarded_user
from app.dependencies.workout_plan import get_workout_plan_service
from app.models.user import User
from app.models.workout_plan import WorkoutPlan, WorkoutPlanAssignment
from app.schemas.workout_plan import (
    WorkoutPlanAssignRequest,
    WorkoutPlanAssignmentRead,
    WorkoutPlanCreate,
    WorkoutPlanPatch,
    WorkoutPlanPut,
    WorkoutPlanRead,
)
from app.services.workout_plan_service import (
    EmptyWorkoutPlanUpdateError,
    InvalidWorkoutPlanAssignmentError,
    WorkoutPlanAssignmentExistsError,
    WorkoutPlanClientNotFoundError,
    WorkoutPlanClientNotManagedError,
    WorkoutPlanNotFoundError,
    WorkoutPlanService,
)

router = APIRouter(tags=["workout-plans"])


@router.post(
    "/workout-plans",
    response_model=WorkoutPlanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create workout plan (coach only)",
)
def create_workout_plan(
    payload: WorkoutPlanCreate,
    current_coach: User = Depends(get_current_coach),
    workout_plan_service: WorkoutPlanService = Depends(get_workout_plan_service),
) -> WorkoutPlan:
    return workout_plan_service.create_plan(current_coach=current_coach, payload=payload)


@router.put(
    "/workout-plans/{plan_id}",
    response_model=WorkoutPlanRead,
    summary="Edit workout plan (coach only)",
)
def put_workout_plan(
    plan_id: UUID,
    payload: WorkoutPlanPut,
    current_coach: User = Depends(get_current_coach),
    workout_plan_service: WorkoutPlanService = Depends(get_workout_plan_service),
) -> WorkoutPlan:
    try:
        return workout_plan_service.replace_plan(
            current_coach=current_coach,
            plan_id=plan_id,
            payload=payload,
        )
    except WorkoutPlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "/workout-plans/{plan_id}",
    response_model=WorkoutPlanRead,
    summary="Partially edit workout plan (coach only)",
)
def patch_workout_plan(
    plan_id: UUID,
    payload: WorkoutPlanPatch,
    current_coach: User = Depends(get_current_coach),
    workout_plan_service: WorkoutPlanService = Depends(get_workout_plan_service),
) -> WorkoutPlan:
    try:
        return workout_plan_service.patch_plan(
            current_coach=current_coach,
            plan_id=plan_id,
            payload=payload,
        )
    except WorkoutPlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except EmptyWorkoutPlanUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/workout-plans/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workout plan (coach only)",
)
def delete_workout_plan(
    plan_id: UUID,
    current_coach: User = Depends(get_current_coach),
    workout_plan_service: WorkoutPlanService = Depends(get_workout_plan_service),
) -> Response:
    try:
        workout_plan_service.delete_plan(current_coach=current_coach, plan_id=plan_id)
    except WorkoutPlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/workout-plans/{plan_id}/assign",
    response_model=WorkoutPlanAssignmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Assign workout plan to client (coach only)",
)
def assign_workout_plan(
    plan_id: UUID,
    payload: WorkoutPlanAssignRequest,
    current_coach: User = Depends(get_current_coach),
    workout_plan_service: WorkoutPlanService = Depends(get_workout_plan_service),
) -> WorkoutPlanAssignment:
    try:
        return workout_plan_service.assign_plan_to_client(
            current_coach=current_coach,
            plan_id=plan_id,
            client_id=payload.client_id,
        )
    except WorkoutPlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WorkoutPlanClientNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WorkoutPlanClientNotManagedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except WorkoutPlanAssignmentExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidWorkoutPlanAssignmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/workout-plans",
    response_model=list[WorkoutPlanRead],
    summary="List workout plans (coach: own plans, client: assigned plans)",
)
def list_workout_plans(
    current_user: User = Depends(get_current_onboarded_user),
    workout_plan_service: WorkoutPlanService = Depends(get_workout_plan_service),
) -> list[WorkoutPlan]:
    return workout_plan_service.list_viewable_plans(current_user=current_user)


@router.get(
    "/workout-plans/{plan_id}",
    response_model=WorkoutPlanRead,
    summary="Get workout plan (coach: own plan, client: assigned plan)",
)
def get_workout_plan(
    plan_id: UUID,
    current_user: User = Depends(get_current_onboarded_user),
    workout_plan_service: WorkoutPlanService = Depends(get_workout_plan_service),
) -> WorkoutPlan:
    try:
        return workout_plan_service.get_viewable_plan(current_user=current_user, plan_id=plan_id)
    except WorkoutPlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc