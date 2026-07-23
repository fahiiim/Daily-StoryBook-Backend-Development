from dataclasses import dataclass
from datetime import date as dt_date
from datetime import datetime, timezone
from uuid import UUID

from app.models.nutrition_plan import NutritionPlan
from app.models.routine import Routine
from app.models.routine_macro_log import MacroType, RoutineMacroLog
from app.models.user import User
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_macro_log_repository import RoutineMacroLogRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.user_repository import UserRepository
from app.schemas.routine import (
    RoutineCreate,
    RoutineMacroLogCreate,
    RoutineMacroLogUpdate,
    RoutinePatch,
    RoutinePut,
)


class RoutineServiceError(Exception):
    pass


class RoutineNotFoundError(RoutineServiceError):
    pass


class RoutineAlreadyExistsError(RoutineServiceError):
    pass


class EmptyRoutineUpdateError(RoutineServiceError):
    pass


class RoutineClientNotFoundError(RoutineServiceError):
    pass


class RoutineClientNotManagedError(RoutineServiceError):
    pass


class RoutineMacroLogNotFoundError(RoutineServiceError):
    pass


@dataclass(frozen=True)
class RoutineRecentFood:
    macro_type: MacroType
    food_name: str
    amount: float
    amount_unit: str
    kcal: float
    protein: float
    carbs: float
    fat: float
    fiber: float
    last_logged_at: datetime


class RoutineService:
    def __init__(
        self,
        routine_repository: RoutineRepository,
        routine_macro_log_repository: RoutineMacroLogRepository | None = None,
        user_repository: UserRepository | None = None,
        coach_client_repository: CoachClientRepository | None = None,
        nutrition_plan_repository: NutritionPlanRepository | None = None,
    ) -> None:
        self.routine_repository = routine_repository
        self.routine_macro_log_repository = routine_macro_log_repository or RoutineMacroLogRepository(
            routine_repository.db
        )
        self.user_repository = user_repository or UserRepository(routine_repository.db)
        self.coach_client_repository = coach_client_repository or CoachClientRepository(routine_repository.db)
        self.nutrition_plan_repository = nutrition_plan_repository or NutritionPlanRepository(routine_repository.db)

    def create_routine(self, *, current_user: User, payload: RoutineCreate) -> Routine:
        self._ensure_unique_daily_routine(user_id=current_user.id, routine_date=payload.date)

        routine = Routine(
            user_id=current_user.id,
            date=payload.date,
            workout=payload.workout,
            meals=payload.meals,
            meals_kcal=None,
            goal_kcal=None,
            goal_protein=None,
            goal_carbs=None,
            goal_fats=None,
            goal_fiber=None,
            intake_protein=None,
            intake_carbs=None,
            intake_fats=None,
            intake_fiber=None,
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

    def get_routine_for_date(self, *, current_user: User, target_date: dt_date) -> Routine | None:
        return self.routine_repository.get_by_user_and_date(
            user_id=current_user.id,
            routine_date=target_date,
        )

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
        macro_type, macro_grams = self._legacy_primary_macro(
            protein=payload.protein,
            carbs=payload.carbs,
            fat=payload.fat,
            fiber=payload.fiber,
        )
        log = RoutineMacroLog(
            routine_id=routine.id,
            user_id=current_user.id,
            macro_type=macro_type,
            meal_type=payload.meal_type,
            food_name=payload.food_name,
            amount=payload.amount,
            amount_unit=payload.amount_unit,
            macro_grams=macro_grams,
            kcal=payload.kcal,
            protein=payload.protein,
            carbs=payload.carbs,
            fat=payload.fat,
            fiber=payload.fiber,
            logged_at=logged_at,
        )

        try:
            saved_log = self.routine_macro_log_repository.create(log=log, commit=False)
            updated_routine = self._recalculate_routine_totals(routine=routine)
            self.routine_repository.db.commit()
            self.routine_repository.db.refresh(updated_routine)
            self.routine_repository.db.refresh(saved_log)
        except Exception:
            self.routine_repository.db.rollback()
            raise

        return updated_routine, saved_log

    def get_client_routine_for_date(
        self,
        *,
        current_coach: User,
        client_id: UUID,
        target_date: dt_date,
    ) -> Routine | None:
        client = self._get_managed_client(current_coach=current_coach, client_id=client_id)
        return self.get_routine_for_date(current_user=client, target_date=target_date)

    def list_client_macro_logs(
        self,
        *,
        current_coach: User,
        client_id: UUID,
        routine_id: UUID,
    ) -> list[RoutineMacroLog]:
        client = self._get_managed_client(current_coach=current_coach, client_id=client_id)
        routine = self.get_routine(current_user=client, routine_id=routine_id)
        return self.routine_macro_log_repository.list_by_routine_for_user(
            routine_id=routine.id,
            user_id=client.id,
        )

    def get_nutrition_plan_for_date(
        self,
        *,
        client_id: UUID,
        routine_date: dt_date,
        coach_id: UUID | None = None,
    ) -> NutritionPlan | None:
        return (
            self.nutrition_plan_repository.get_active_by_coach_client_date(
                coach_id=coach_id,
                client_id=client_id,
                plan_date=routine_date,
            )
            if coach_id is not None
            else self.nutrition_plan_repository.get_active_by_client_date(
                client_id=client_id,
                plan_date=routine_date,
            )
        )

    def update_macro_log(
        self,
        *,
        current_user: User,
        routine_id: UUID,
        log_id: UUID,
        payload: RoutineMacroLogUpdate,
    ) -> tuple[Routine, RoutineMacroLog]:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)
        log = self.routine_macro_log_repository.get_by_id_for_routine_user(
            log_id=log_id,
            routine_id=routine.id,
            user_id=current_user.id,
        )
        if log is None:
            raise RoutineMacroLogNotFoundError("Logged meal not found")

        updates = payload.model_dump(exclude_unset=True)
        nutrient_fields = {"protein", "carbs", "fat", "fiber"}
        if nutrient_fields.intersection(updates):
            nutrient_values = {
                field_name: float(updates.get(field_name, getattr(log, field_name)))
                for field_name in nutrient_fields
            }
            macro_type, macro_grams = self._legacy_primary_macro(**nutrient_values)
            updates.update({"macro_type": macro_type, "macro_grams": macro_grams})

        try:
            updated_log = self.routine_macro_log_repository.update_fields(
                log=log,
                updates=updates,
                commit=False,
            )
            updated_routine = self._recalculate_routine_totals(routine=routine)
            self.routine_repository.db.commit()
            self.routine_repository.db.refresh(updated_routine)
            self.routine_repository.db.refresh(updated_log)
        except Exception:
            self.routine_repository.db.rollback()
            raise

        return updated_routine, updated_log

    def delete_macro_log(
        self,
        *,
        current_user: User,
        routine_id: UUID,
        log_id: UUID,
    ) -> Routine:
        routine = self.get_routine(current_user=current_user, routine_id=routine_id)
        log = self.routine_macro_log_repository.get_by_id_for_routine_user(
            log_id=log_id,
            routine_id=routine.id,
            user_id=current_user.id,
        )
        if log is None:
            raise RoutineMacroLogNotFoundError("Logged meal not found")

        try:
            self.routine_macro_log_repository.delete(log=log, commit=False)
            updated_routine = self._recalculate_routine_totals(routine=routine)
            self.routine_repository.db.commit()
            self.routine_repository.db.refresh(updated_routine)
        except Exception:
            self.routine_repository.db.rollback()
            raise

        return updated_routine

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
                    macro_type=macro_type,
                    food_name=log.food_name,
                    amount=log.amount,
                    amount_unit=log.amount_unit,
                    kcal=log.kcal,
                    protein=log.protein,
                    carbs=log.carbs,
                    fat=log.fat,
                    fiber=log.fiber,
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

    def _recalculate_routine_totals(self, *, routine: Routine) -> Routine:
        logs = self.routine_macro_log_repository.list_by_routine_for_user(
            routine_id=routine.id,
            user_id=routine.user_id,
        )
        return self.routine_repository.update_fields(
            routine=routine,
            updates={
                "meals_kcal": round(sum(log.kcal for log in logs), 2),
                "intake_protein": round(sum(log.protein for log in logs), 2),
                "intake_carbs": round(sum(log.carbs for log in logs), 2),
                "intake_fats": round(sum(log.fat for log in logs), 2),
                "intake_fiber": round(sum(log.fiber for log in logs), 2),
            },
            commit=False,
        )

    @staticmethod
    def _legacy_primary_macro(
        *,
        protein: float,
        carbs: float,
        fat: float,
        fiber: float,
    ) -> tuple[MacroType, float]:
        macro_values = {
            MacroType.PROTEIN: protein,
            MacroType.CARBS: carbs,
            MacroType.FATS: fat,
            MacroType.FIBER: fiber,
        }
        macro_type = max(macro_values, key=macro_values.get)
        return macro_type, round(macro_values[macro_type], 2)

    def _get_managed_client(self, *, current_coach: User, client_id: UUID) -> User:
        client = self.user_repository.get_by_id(client_id)
        if client is None:
            raise RoutineClientNotFoundError("Client not found")

        if not self.coach_client_repository.accepted_relationship_exists(
            coach_id=current_coach.id,
            client_id=client_id,
        ):
            raise RoutineClientNotManagedError("Client is not assigned to this coach")

        return client