from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.dependencies.auth import get_current_coach, get_current_user
from app.dependencies.nutrition_plan import get_nutrition_plan_service
from app.models.nutrition_plan import NutritionPlan
from app.models.user import User
from app.schemas.nutrition_plan import NutritionPlanCreate, NutritionPlanPut, NutritionPlanRead
from app.services.nutrition_plan_service import (
    NutritionPlanClientNotFoundError,
    NutritionPlanClientNotManagedError,
    NutritionPlanNotFoundError,
    NutritionPlanService,
)

router = APIRouter(prefix="/coach", tags=["nutrition-plans"])


@router.post(
    "/nutrition-plans",
    response_model=NutritionPlanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create nutrition plan (coach only)",
)
def create_nutrition_plan(
    payload: NutritionPlanCreate,
    current_coach: User = Depends(get_current_coach),
    nutrition_plan_service: NutritionPlanService = Depends(get_nutrition_plan_service),
) -> NutritionPlan:
    try:
        return nutrition_plan_service.create_plan(current_coach=current_coach, payload=payload)
    except NutritionPlanClientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except NutritionPlanClientNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/nutrition-plans",
    response_model=list[NutritionPlanRead],
    summary="List nutrition plans (coach: own plans, client: assigned plans)",
)
def list_nutrition_plans(
    current_user: User = Depends(get_current_user),
    nutrition_plan_service: NutritionPlanService = Depends(get_nutrition_plan_service),
) -> list[NutritionPlan]:
    return nutrition_plan_service.list_viewable_plans(current_user=current_user)


@router.get(
    "/nutrition-plans/{plan_id}",
    response_model=NutritionPlanRead,
    summary="Get nutrition plan by id (coach own, client assigned)",
)
def get_nutrition_plan(
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    nutrition_plan_service: NutritionPlanService = Depends(get_nutrition_plan_service),
) -> NutritionPlan:
    try:
        return nutrition_plan_service.get_viewable_plan(current_user=current_user, plan_id=plan_id)
    except NutritionPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/nutrition-plans/{plan_id}",
    response_model=NutritionPlanRead,
    summary="Update nutrition plan (coach only)",
)
def put_nutrition_plan(
    plan_id: UUID,
    payload: NutritionPlanPut,
    current_coach: User = Depends(get_current_coach),
    nutrition_plan_service: NutritionPlanService = Depends(get_nutrition_plan_service),
) -> NutritionPlan:
    try:
        return nutrition_plan_service.replace_plan(
            current_coach=current_coach,
            plan_id=plan_id,
            payload=payload,
        )
    except NutritionPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except NutritionPlanClientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except NutritionPlanClientNotManagedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.delete(
    "/nutrition-plans/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete nutrition plan (coach only)",
)
def delete_nutrition_plan(
    plan_id: UUID,
    current_coach: User = Depends(get_current_coach),
    nutrition_plan_service: NutritionPlanService = Depends(get_nutrition_plan_service),
) -> Response:
    try:
        nutrition_plan_service.delete_plan(current_coach=current_coach, plan_id=plan_id)
    except NutritionPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)