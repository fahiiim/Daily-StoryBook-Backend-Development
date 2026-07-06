from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.ai import get_ai_service
from app.dependencies.db import get_db_session
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.storybook_repository import StorybookRepository
from app.repositories.user_repository import UserRepository
from app.repositories.weekly_summary_repository import WeeklySummaryRepository
from app.repositories.workout_plan_repository import WorkoutPlanRepository
from app.services.ai_service import AIService
from app.services.weekly_summary_service import WeeklySummaryService


def get_weekly_summary_service(
    db: Session = Depends(get_db_session),
    ai_service: AIService = Depends(get_ai_service),
) -> WeeklySummaryService:
    return WeeklySummaryService(
        db=db,
        ai_service=ai_service,
        weekly_summary_repository=WeeklySummaryRepository(db),
        routine_repository=RoutineRepository(db),
        workout_plan_repository=WorkoutPlanRepository(db),
        nutrition_plan_repository=NutritionPlanRepository(db),
        storybook_repository=StorybookRepository(db),
        user_repository=UserRepository(db),
        coach_client_repository=CoachClientRepository(db),
    )