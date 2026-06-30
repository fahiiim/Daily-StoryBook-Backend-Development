from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_plan_repository import WorkoutPlanRepository
from app.services.workout_plan_service import WorkoutPlanService


def get_workout_plan_service(db: Session = Depends(get_db_session)) -> WorkoutPlanService:
    return WorkoutPlanService(
        workout_plan_repository=WorkoutPlanRepository(db),
        user_repository=UserRepository(db),
        coach_client_repository=CoachClientRepository(db),
    )