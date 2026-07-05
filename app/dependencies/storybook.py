from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.ai import get_ai_service
from app.dependencies.db import get_db_session
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.storybook_repository import StorybookRepository, StoryPageRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_plan_repository import WorkoutPlanRepository
from app.services.ai_service import AIService
from app.services.storybook_service import StorybookService


def get_storybook_service(
    db: Session = Depends(get_db_session),
    ai_service: AIService = Depends(get_ai_service),
) -> StorybookService:
    return StorybookService(
        db=db,
        ai_service=ai_service,
        storybook_repository=StorybookRepository(db),
        story_page_repository=StoryPageRepository(db),
        routine_repository=RoutineRepository(db),
        nutrition_plan_repository=NutritionPlanRepository(db),
        workout_plan_repository=WorkoutPlanRepository(db),
        user_repository=UserRepository(db),
        coach_client_repository=CoachClientRepository(db),
    )
