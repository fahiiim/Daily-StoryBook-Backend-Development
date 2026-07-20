from uuid import UUID

from app.models.nutrition_plan import NutritionPlan
from app.models.user import User, UserRole
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.user_repository import UserRepository
from app.schemas.nutrition_plan import NutritionPlanCreate, NutritionPlanPut


class NutritionPlanServiceError(Exception):
    pass


class NutritionPlanNotFoundError(NutritionPlanServiceError):
    pass


class NutritionPlanClientNotFoundError(NutritionPlanServiceError):
    pass


class NutritionPlanClientNotManagedError(NutritionPlanServiceError):
    pass


class NutritionPlanAlreadyExistsError(NutritionPlanServiceError):
    pass


class NutritionPlanService:
    def __init__(
        self,
        *,
        nutrition_plan_repository: NutritionPlanRepository,
        user_repository: UserRepository,
        coach_client_repository: CoachClientRepository,
    ) -> None:
        self.nutrition_plan_repository = nutrition_plan_repository
        self.user_repository = user_repository
        self.coach_client_repository = coach_client_repository

    def create_plan(self, *, current_coach: User, payload: NutritionPlanCreate) -> NutritionPlan:
        self._ensure_coach_role(current_coach)
        self._ensure_client_accessible(coach_id=current_coach.id, client_id=payload.client_id)
        self._ensure_unique_daily_client_plan(
            coach_id=current_coach.id,
            client_id=payload.client_id,
            plan_date=payload.date,
        )

        plan = NutritionPlan(
            coach_id=current_coach.id,
            client_id=payload.client_id,
            daily_calories=payload.daily_calories,
            protein=payload.protein,
            carbs=payload.carbs,
            fat=payload.fat,
            fiber=payload.fiber,
            water_goal=payload.water_goal,
            workout_plan=list(payload.workout_plan),
            daily_goals=list(payload.daily_goals),
            notes=payload.notes,
            date=payload.date,
        )
        return self.nutrition_plan_repository.create(plan=plan)

    def list_viewable_plans(self, *, current_user: User) -> list[NutritionPlan]:
        if current_user.role == UserRole.COACH:
            return self.nutrition_plan_repository.list_by_coach(coach_id=current_user.id)
        return self.nutrition_plan_repository.list_by_client(client_id=current_user.id)

    def get_viewable_plan(self, *, current_user: User, plan_id: UUID) -> NutritionPlan:
        if current_user.role == UserRole.COACH:
            plan = self.nutrition_plan_repository.get_by_id_for_coach(
                plan_id=plan_id,
                coach_id=current_user.id,
            )
        else:
            plan = self.nutrition_plan_repository.get_by_id_for_client(
                plan_id=plan_id,
                client_id=current_user.id,
            )

        if plan is None:
            raise NutritionPlanNotFoundError("Nutrition plan not found")
        return plan

    def replace_plan(
        self,
        *,
        current_coach: User,
        plan_id: UUID,
        payload: NutritionPlanPut,
    ) -> NutritionPlan:
        self._ensure_coach_role(current_coach)
        plan = self._get_owned_plan(coach_id=current_coach.id, plan_id=plan_id)
        self._ensure_client_accessible(coach_id=current_coach.id, client_id=payload.client_id)
        self._ensure_unique_daily_client_plan(
            coach_id=current_coach.id,
            client_id=payload.client_id,
            plan_date=payload.date,
            exclude_plan_id=plan.id,
        )

        updates = payload.model_dump()
        updates["workout_plan"] = list(payload.workout_plan)
        updates["daily_goals"] = list(payload.daily_goals)
        return self.nutrition_plan_repository.update_fields(plan=plan, updates=updates)

    def delete_plan(self, *, current_coach: User, plan_id: UUID) -> None:
        self._ensure_coach_role(current_coach)
        plan = self._get_owned_plan(coach_id=current_coach.id, plan_id=plan_id)
        self.nutrition_plan_repository.delete(plan=plan)

    def _ensure_client_accessible(self, *, coach_id: UUID, client_id: UUID) -> None:
        client = self.user_repository.get_by_id(client_id)
        if client is None:
            raise NutritionPlanClientNotFoundError("Client not found")

        relationship_exists = self.coach_client_repository.accepted_relationship_exists(
            coach_id=coach_id,
            client_id=client_id,
        )
        if not relationship_exists:
            raise NutritionPlanClientNotManagedError("Client is not assigned to this coach")

    def _ensure_unique_daily_client_plan(
        self,
        *,
        coach_id: UUID,
        client_id: UUID,
        plan_date,
        exclude_plan_id: UUID | None = None,
    ) -> None:
        existing = self.nutrition_plan_repository.get_by_coach_client_date(
            coach_id=coach_id,
            client_id=client_id,
            plan_date=plan_date,
        )
        if existing is None:
            return

        if exclude_plan_id is not None and existing.id == exclude_plan_id:
            return

        raise NutritionPlanAlreadyExistsError(
            "Only one nutrition plan is allowed per client per day"
        )

    def _get_owned_plan(self, *, coach_id: UUID, plan_id: UUID) -> NutritionPlan:
        plan = self.nutrition_plan_repository.get_by_id_for_coach(
            plan_id=plan_id,
            coach_id=coach_id,
        )
        if plan is None:
            raise NutritionPlanNotFoundError("Nutrition plan not found")
        return plan

    @staticmethod
    def _ensure_coach_role(current_user: User) -> None:
        if current_user.role != UserRole.COACH:
            raise NutritionPlanServiceError("Coach role required")