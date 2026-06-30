from uuid import UUID

from app.models.routine import Routine
from app.models.user import User
from app.repositories.routine_repository import RoutineRepository
from app.schemas.routine import RoutineCreate, RoutinePatch, RoutinePut


class RoutineServiceError(Exception):
    pass


class RoutineNotFoundError(RoutineServiceError):
    pass


class RoutineAlreadyExistsError(RoutineServiceError):
    pass


class EmptyRoutineUpdateError(RoutineServiceError):
    pass


class RoutineService:
    def __init__(self, routine_repository: RoutineRepository) -> None:
        self.routine_repository = routine_repository

    def create_routine(self, *, current_user: User, payload: RoutineCreate) -> Routine:
        self._ensure_unique_daily_routine(user_id=current_user.id, routine_date=payload.date)

        routine = Routine(
            user_id=current_user.id,
            date=payload.date,
            workout=payload.workout,
            meals=payload.meals,
            water_intake=payload.water_intake,
            sleep=payload.sleep,
            notes=payload.notes,
            completion_status=payload.completion_status,
        )
        return self.routine_repository.create(routine=routine)

    def list_routines(self, *, current_user: User) -> list[Routine]:
        return self.routine_repository.list_by_user(user_id=current_user.id)

    def get_routine(self, *, current_user: User, routine_id: UUID) -> Routine:
        routine = self.routine_repository.get_by_id_for_user(
            routine_id=routine_id,
            user_id=current_user.id,
        )
        if routine is None:
            raise RoutineNotFoundError("Routine not found")
        return routine

    def replace_routine(
        self,
        *,
        current_user: User,
        routine_id: UUID,
        payload: RoutinePut,
    ) -> Routine:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)
        self._ensure_unique_daily_routine(
            user_id=current_user.id,
            routine_date=payload.date,
            exclude_routine_id=routine.id,
        )

        updates = payload.model_dump()
        return self.routine_repository.update_fields(routine=routine, updates=updates)

    def patch_routine(
        self,
        *,
        current_user: User,
        routine_id: UUID,
        payload: RoutinePatch,
    ) -> Routine:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise EmptyRoutineUpdateError("No routine fields were provided")

        if "date" in updates:
            self._ensure_unique_daily_routine(
                user_id=current_user.id,
                routine_date=updates["date"],
                exclude_routine_id=routine.id,
            )

        return self.routine_repository.update_fields(routine=routine, updates=updates)

    def delete_routine(self, *, current_user: User, routine_id: UUID) -> None:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)
        self.routine_repository.delete(routine=routine)

    def _ensure_unique_daily_routine(
        self,
        *,
        user_id: UUID,
        routine_date,
        exclude_routine_id: UUID | None = None,
    ) -> None:
        existing = self.routine_repository.get_by_user_and_date(
            user_id=user_id,
            routine_date=routine_date,
        )
        if existing is None:
            return

        if exclude_routine_id is not None and existing.id == exclude_routine_id:
            return

        raise RoutineAlreadyExistsError("Only one routine is allowed per user per day")