from dataclasses import dataclass
from datetime import date as dt_date
from datetime import datetime, timezone
from uuid import UUID

from app.models.routine import Routine
from app.models.routine_macro_log import MacroType, RoutineMacroLog
from app.models.user import User
from app.repositories.routine_macro_log_repository import RoutineMacroLogRepository
from app.repositories.routine_repository import RoutineRepository
from app.schemas.routine import RoutineCreate, RoutineMacroLogCreate, RoutinePatch, RoutinePut


class RoutineServiceError(Exception):
    pass


class RoutineNotFoundError(RoutineServiceError):
    pass


class RoutineAlreadyExistsError(RoutineServiceError):
    pass


class EmptyRoutineUpdateError(RoutineServiceError):
    pass


@dataclass(frozen=True)
class RoutineRecentFood:
    macro_type: MacroType
    food_name: str
    amount: float
    amount_unit: str
    macro_grams: float
    kcal: float
    last_logged_at: datetime


class RoutineService:
    def __init__(
        self,
        routine_repository: RoutineRepository,
        routine_macro_log_repository: RoutineMacroLogRepository | None = None,
    ) -> None:
        self.routine_repository = routine_repository
        self.routine_macro_log_repository = routine_macro_log_repository or RoutineMacroLogRepository(
            routine_repository.db
        )

    def create_routine(self, *, current_user: User, payload: RoutineCreate) -> Routine:
        self._ensure_unique_daily_routine(user_id=current_user.id, routine_date=payload.date)

        routine = Routine(
            user_id=current_user.id,
            date=payload.date,
            workout=payload.workout,
            meals=payload.meals,
            meals_kcal=payload.meals_kcal,
            goal_kcal=payload.goal_kcal,
            goal_protein=payload.goal_protein,
            goal_carbs=payload.goal_carbs,
            goal_fats=payload.goal_fats,
            goal_fiber=payload.goal_fiber,
            intake_protein=payload.intake_protein,
            intake_carbs=payload.intake_carbs,
            intake_fats=payload.intake_fats,
            intake_fiber=payload.intake_fiber,
            water_intake=payload.water_intake,
            sleep=payload.sleep,
            notes=payload.notes,
            completion_status=payload.completion_status,
        )
        return self.routine_repository.create(routine=routine)

    def list_routines(self, *, current_user: User) -> list[Routine]:
        return self.routine_repository.list_by_user(user_id=current_user.id)

    def get_or_create_routine_for_date(
        self,
        *,
        current_user: User,
        target_date: dt_date,
    ) -> Routine:
        existing = self.routine_repository.get_by_user_and_date(
            user_id=current_user.id,
            routine_date=target_date,
        )
        if existing is not None:
            return existing

        routine = Routine(
            user_id=current_user.id,
            date=target_date,
            completion_status=False,
        )
        return self.routine_repository.create(routine=routine)

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

    def add_macro_log(
        self,
        *,
        current_user: User,
        routine_id: UUID,
        payload: RoutineMacroLogCreate,
    ) -> tuple[Routine, RoutineMacroLog]:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)

        logged_at = payload.logged_at or datetime.now(tz=timezone.utc)
        log = RoutineMacroLog(
            routine_id=routine.id,
            user_id=current_user.id,
            macro_type=payload.macro_type,
            food_name=payload.food_name.strip(),
            amount=payload.amount,
            amount_unit=payload.amount_unit.strip(),
            macro_grams=payload.macro_grams,
            kcal=payload.kcal,
            logged_at=logged_at,
        )

        intake_field_map: dict[MacroType, str] = {
            MacroType.PROTEIN: "intake_protein",
            MacroType.CARBS: "intake_carbs",
            MacroType.FATS: "intake_fats",
            MacroType.FIBER: "intake_fiber",
        }
        intake_field = intake_field_map[payload.macro_type]
        updated_intake = round((getattr(routine, intake_field) or 0.0) + payload.macro_grams, 2)
        updated_meals_kcal = round((routine.meals_kcal or 0.0) + payload.kcal, 2)

        try:
            saved_log = self.routine_macro_log_repository.create(log=log, commit=False)
            updated_routine = self.routine_repository.update_fields(
                routine=routine,
                updates={
                    intake_field: updated_intake,
                    "meals_kcal": updated_meals_kcal,
                },
                commit=False,
            )
            self.routine_repository.db.commit()
        except Exception:
            self.routine_repository.db.rollback()
            raise

        return updated_routine, saved_log

    def list_macro_logs(self, *, current_user: User, routine_id: UUID) -> list[RoutineMacroLog]:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)
        return self.routine_macro_log_repository.list_by_routine_for_user(
            routine_id=routine.id,
            user_id=current_user.id,
        )

    def list_recent_macro_foods(
        self,
        *,
        current_user: User,
        macro_type: MacroType,
        limit: int,
    ) -> list[RoutineRecentFood]:
        logs = self.routine_macro_log_repository.list_by_user_and_macro_type(
            user_id=current_user.id,
            macro_type=macro_type,
            limit=max(limit * 10, limit),
        )

        seen_foods: set[str] = set()
        recent: list[RoutineRecentFood] = []
        for log in logs:
            key = log.food_name.strip().lower()
            if key in seen_foods:
                continue
            seen_foods.add(key)

            recent.append(
                RoutineRecentFood(
                    macro_type=log.macro_type,
                    food_name=log.food_name,
                    amount=log.amount,
                    amount_unit=log.amount_unit,
                    macro_grams=log.macro_grams,
                    kcal=log.kcal,
                    last_logged_at=log.logged_at,
                )
            )
            if len(recent) >= limit:
                break

        return recent

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