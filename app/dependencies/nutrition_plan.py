from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.user_repository import UserRepository
from app.services.nutrition_plan_service import NutritionPlanService


def get_nutrition_plan_service(db: Session = Depends(get_db_session)) -> NutritionPlanService:
    return NutritionPlanService(
        nutrition_plan_repository=NutritionPlanRepository(db),
        user_repository=UserRepository(db),
        coach_client_repository=CoachClientRepository(db),
    )