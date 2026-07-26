from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.daily_goal_repository import DailyGoalCompletionRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_macro_log_repository import RoutineMacroLogRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_plan_repository import WorkoutPlanCompletionRepository
from app.services.weekly_summary_service import WeeklySummaryService


def get_weekly_summary_service(
    db: Session = Depends(get_db_session),
) -> WeeklySummaryService:
    return WeeklySummaryService(
        routine_repository=RoutineRepository(db),
        routine_macro_log_repository=RoutineMacroLogRepository(db),
        workout_plan_repository=WorkoutPlanCompletionRepository(db),
        daily_goal_repository=DailyGoalCompletionRepository(db),
        nutrition_plan_repository=NutritionPlanRepository(db),
        user_repository=UserRepository(db),
        coach_client_repository=CoachClientRepository(db),
    )