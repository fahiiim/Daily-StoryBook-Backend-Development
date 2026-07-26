from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.dependencies.workout_plan import get_workout_plan_service
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.storybook_repository import StorybookRepository
from app.repositories.user_repository import UserRepository
from app.services.dashboard_service import DashboardService
from app.services.workout_plan_service import WorkoutPlanService


def get_dashboard_service(
    db: Session = Depends(get_db_session),
    workout_plan_service: WorkoutPlanService = Depends(get_workout_plan_service),
) -> DashboardService:
    return DashboardService(
        dashboard_repository=DashboardRepository(db),
        routine_repository=RoutineRepository(db),
        storybook_repository=StorybookRepository(db),
        workout_plan_service=workout_plan_service,
        nutrition_plan_repository=NutritionPlanRepository(db),
        user_repository=UserRepository(db),
        coach_client_repository=CoachClientRepository(db),
    )
