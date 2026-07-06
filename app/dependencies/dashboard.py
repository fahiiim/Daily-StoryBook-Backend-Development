from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.dependencies.weekly_summary import get_weekly_summary_service
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.storybook_repository import StorybookRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_plan_repository import WorkoutPlanRepository
from app.services.dashboard_service import DashboardService
from app.services.weekly_summary_service import WeeklySummaryService


def get_dashboard_service(
    db: Session = Depends(get_db_session),
    weekly_summary_service: WeeklySummaryService = Depends(get_weekly_summary_service),
) -> DashboardService:
    return DashboardService(
        dashboard_repository=DashboardRepository(db),
        routine_repository=RoutineRepository(db),
        storybook_repository=StorybookRepository(db),
        workout_plan_repository=WorkoutPlanRepository(db),
        nutrition_plan_repository=NutritionPlanRepository(db),
        user_repository=UserRepository(db),
        coach_client_repository=CoachClientRepository(db),
        weekly_summary_service=weekly_summary_service,
    )
