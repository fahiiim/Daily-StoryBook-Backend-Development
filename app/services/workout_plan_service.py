from datetime import date, datetime, timezone
from uuid import UUID, uuid5

from app.models.nutrition_plan import NutritionPlan, nutrition_plan_valid_until
from app.models.user import User, UserRole
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_plan_repository import WorkoutPlanCompletionRepository
from app.schemas.workout_plan import AssignedWorkoutItemRead, AssignedWorkoutPlanRead


WORKOUT_ITEM_NAMESPACE = UUID("d606bf8e-f5a5-4d53-a32e-dc42fb883f11")


def build_workout_item_id(
    *,
    nutrition_plan_id: UUID,
    position: int,
    instruction: str,
) -> UUID:
    return uuid5(WORKOUT_ITEM_NAMESPACE, f"{nutrition_plan_id}:{position}:{instruction}")


class WorkoutPlanServiceError(Exception):
    pass


class WorkoutPlanNotFoundError(WorkoutPlanServiceError):
    pass


class WorkoutItemNotFoundError(WorkoutPlanServiceError):
    pass


class WorkoutPlanClientNotFoundError(WorkoutPlanServiceError):
    pass


class WorkoutPlanClientNotManagedError(WorkoutPlanServiceError):
    pass


class WorkoutPlanService:
    def __init__(
        self,
        *,
        completion_repository: WorkoutPlanCompletionRepository,
        nutrition_plan_repository: NutritionPlanRepository,
        user_repository: UserRepository,
        coach_client_repository: CoachClientRepository,
    ) -> None:
        self.completion_repository = completion_repository
        self.nutrition_plan_repository = nutrition_plan_repository
        self.user_repository = user_repository
        self.coach_client_repository = coach_client_repository

    def get_assigned_plan(
        self,
        *,
        current_user: User,
        target_date: date | None = None,
    ) -> AssignedWorkoutPlanRead:
        if current_user.role != UserRole.SELF:
            raise WorkoutPlanServiceError("SELF role required")

        plan_date = target_date or date.today()
        plan = self.nutrition_plan_repository.get_active_by_client_date(
            client_id=current_user.id,
            plan_date=plan_date,
        )
        if plan is None:
            raise WorkoutPlanNotFoundError("No active workout plan assigned")
        return self._build_progress(plan=plan, client_id=current_user.id)

    def get_assigned_plan_for_client(
        self,
        *,
        current_coach: User,
        client_id: UUID,
        target_date: date | None = None,
    ) -> AssignedWorkoutPlanRead:
        client = self.user_repository.get_by_id(client_id)
        if client is None or client.role != UserRole.SELF:
            raise WorkoutPlanClientNotFoundError("Client not found")
        if not self.coach_client_repository.accepted_relationship_exists(
            coach_id=current_coach.id,
            client_id=client_id,
        ):
            raise WorkoutPlanClientNotManagedError("Client is not assigned to this coach")

        plan_date = target_date or date.today()
        plan = self.nutrition_plan_repository.get_active_by_coach_client_date(
            coach_id=current_coach.id,
            client_id=client_id,
            plan_date=plan_date,
        )
        if plan is None:
            raise WorkoutPlanNotFoundError("No active workout plan assigned")
        return self._build_progress(plan=plan, client_id=client_id)

    def update_completion(
        self,
        *,
        current_user: User,
        workout_item_id: UUID,
        completed: bool,
        target_date: date | None = None,
    ) -> AssignedWorkoutItemRead:
        progress = self.get_assigned_plan(current_user=current_user, target_date=target_date)
        item = next((item for item in progress.items if item.id == workout_item_id), None)
        if item is None:
            raise WorkoutItemNotFoundError("Assigned workout item not found")

        completed_at = datetime.now(tz=timezone.utc) if completed else None
        completion = self.completion_repository.set_completion(
            nutrition_plan_id=progress.nutrition_plan_id,
            client_id=current_user.id,
            workout_item_id=workout_item_id,
            completed=completed,
            completed_at=completed_at,
        )
        return item.model_copy(
            update={
                "completed": completion.is_completed,
                "completed_at": completion.completed_at,
            }
        )

    def _build_progress(
        self,
        *,
        plan: NutritionPlan,
        client_id: UUID,
    ) -> AssignedWorkoutPlanRead:
        completions = self.completion_repository.list_by_plan_for_client(
            nutrition_plan_id=plan.id,
            client_id=client_id,
        )
        completion_by_item = {item.workout_item_id: item for item in completions}
        items: list[AssignedWorkoutItemRead] = []
        for position, instruction in enumerate(plan.workout_plan):
            item_id = build_workout_item_id(
                nutrition_plan_id=plan.id,
                position=position,
                instruction=instruction,
            )
            completion = completion_by_item.get(item_id)
            items.append(
                AssignedWorkoutItemRead(
                    id=item_id,
                    position=position,
                    instruction=instruction,
                    completed=bool(completion and completion.is_completed),
                    completed_at=completion.completed_at if completion and completion.is_completed else None,
                )
            )

        completed_count = sum(1 for item in items if item.completed)
        total_count = len(items)
        completion_rate = round((completed_count / total_count) * 100, 2) if total_count else 0.0
        return AssignedWorkoutPlanRead(
            nutrition_plan_id=plan.id,
            coach_id=plan.coach_id,
            client_id=client_id,
            valid_from=plan.date,
            valid_until=nutrition_plan_valid_until(plan.date),
            validity_days=7,
            items=items,
            completed_count=completed_count,
            total_count=total_count,
            completion_rate=completion_rate,
            all_completed=total_count > 0 and completed_count == total_count,
        )
