from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_coach, get_current_self
from app.dependencies.workout_plan import get_workout_plan_service
from app.models.user import User
from app.schemas.workout_plan import (
    AssignedWorkoutItemRead,
    AssignedWorkoutPlanRead,
    WorkoutCompletionUpdate,
)
from app.services.workout_plan_service import (
    WorkoutItemNotFoundError,
    WorkoutPlanClientNotFoundError,
    WorkoutPlanClientNotManagedError,
    WorkoutPlanNotFoundError,
    WorkoutPlanService,
)

router = APIRouter(tags=["workout-plans"])


@router.get(
    "/workout-plans/assigned",
    response_model=AssignedWorkoutPlanRead,
    summary="Get current assigned workout plan",
)
def get_assigned_workout_plan(
    current_user: User = Depends(get_current_self),
    workout_plan_service: WorkoutPlanService = Depends(get_workout_plan_service),
) -> AssignedWorkoutPlanRead:
    try:
        return workout_plan_service.get_assigned_plan(current_user=current_user)
    except WorkoutPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch(
    "/workout-plans/assigned/{workout_item_id}",
    response_model=AssignedWorkoutItemRead,
    summary="Mark or unmark an assigned workout item",
)
def update_assigned_workout_completion(
    workout_item_id: UUID,
    payload: WorkoutCompletionUpdate,
    current_user: User = Depends(get_current_self),
    workout_plan_service: WorkoutPlanService = Depends(get_workout_plan_service),
) -> AssignedWorkoutItemRead:
    try:
        return workout_plan_service.update_completion(
            current_user=current_user,
            workout_item_id=workout_item_id,
            completed=payload.completed,
        )
    except WorkoutPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WorkoutItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/coach/clients/{client_id}/workout-plans/assigned",
    response_model=AssignedWorkoutPlanRead,
    summary="View managed client's assigned workout progress",
)
def get_client_assigned_workout_plan(
    client_id: UUID,
    current_coach: User = Depends(get_current_coach),
    workout_plan_service: WorkoutPlanService = Depends(get_workout_plan_service),
) -> AssignedWorkoutPlanRead:
    try:
        return workout_plan_service.get_assigned_plan_for_client(
            current_coach=current_coach,
            client_id=client_id,
        )
    except WorkoutPlanClientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WorkoutPlanClientNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except WorkoutPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
