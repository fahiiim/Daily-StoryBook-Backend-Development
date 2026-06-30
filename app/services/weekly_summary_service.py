from datetime import date, timedelta

from app.models.user import User
from app.repositories.routine_repository import RoutineRepository
from app.schemas.weekly_summary import WeeklySummaryResponse


class WeeklySummaryService:
    def __init__(self, routine_repository: RoutineRepository) -> None:
        self.routine_repository = routine_repository

    def get_weekly_summary(
        self,
        *,
        current_user: User,
        week_start: date | None = None,
    ) -> WeeklySummaryResponse:
        if week_start is None:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())

        week_end = week_start + timedelta(days=6)
        routines = self.routine_repository.list_by_user_between_dates(
            user_id=current_user.id,
            start_date=week_start,
            end_date=week_end,
        )

        total_routines = len(routines)
        completed_routines = sum(1 for routine in routines if routine.completion_status)
        completion_rate = round((completed_routines / total_routines) * 100, 2) if total_routines else 0.0

        water_values = [routine.water_intake for routine in routines if routine.water_intake is not None]
        sleep_values = [routine.sleep for routine in routines if routine.sleep is not None]

        average_water_intake = round(sum(water_values) / len(water_values), 2) if water_values else None
        average_sleep = round(sum(sleep_values) / len(sleep_values), 2) if sleep_values else None

        workout_entries = sum(1 for routine in routines if routine.workout)
        meal_entries = sum(1 for routine in routines if routine.meals)
        notes_entries = sum(1 for routine in routines if routine.notes)

        return WeeklySummaryResponse(
            week_start=week_start,
            week_end=week_end,
            total_routines=total_routines,
            completed_routines=completed_routines,
            completion_rate=completion_rate,
            average_water_intake=average_water_intake,
            average_sleep=average_sleep,
            workout_entries=workout_entries,
            meal_entries=meal_entries,
            notes_entries=notes_entries,
        )