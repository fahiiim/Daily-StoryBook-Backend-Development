from uuid import UUID

from app.models.user import User, UserRole
from app.models.workout_plan import WorkoutPlan, WorkoutPlanAssignment
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_plan_repository import WorkoutPlanRepository
from app.schemas.workout_plan import WorkoutPlanCreate, WorkoutPlanPatch, WorkoutPlanPut


class WorkoutPlanServiceError(Exception):
    pass


class WorkoutPlanNotFoundError(WorkoutPlanServiceError):
    pass


class WorkoutPlanAssignmentExistsError(WorkoutPlanServiceError):
    pass


class WorkoutPlanClientNotFoundError(WorkoutPlanServiceError):
    pass


class WorkoutPlanClientNotManagedError(WorkoutPlanServiceError):
    pass


class EmptyWorkoutPlanUpdateError(WorkoutPlanServiceError):
    pass


class InvalidWorkoutPlanAssignmentError(WorkoutPlanServiceError):
    pass


class WorkoutPlanService:
    def __init__(
        self,
        *,
        workout_plan_repository: WorkoutPlanRepository,
        user_repository: UserRepository,
        coach_client_repository: CoachClientRepository,
    ) -> None:
        self.workout_plan_repository = workout_plan_repository
        self.user_repository = user_repository
        self.coach_client_repository = coach_client_repository

    def create_plan(self, *, current_coach: User, payload: WorkoutPlanCreate) -> WorkoutPlan:
        self._ensure_coach_role(current_coach)

        plan = WorkoutPlan(
            coach_id=current_coach.id,
            title=payload.title,
            description=payload.description,
            exercises=list(payload.exercises),
            is_active=payload.is_active,
        )
        return self.workout_plan_repository.create_plan(plan=plan)

    def replace_plan(
        self,
        *,
        current_coach: User,
        plan_id: UUID,
        payload: WorkoutPlanPut,
    ) -> WorkoutPlan:
        self._ensure_coach_role(current_coach)
        plan = self._get_owned_plan(coach_id=current_coach.id, plan_id=plan_id)
        updates = payload.model_dump()
        updates["exercises"] = list(payload.exercises)
        return self.workout_plan_repository.update_plan_fields(plan=plan, updates=updates)

    def patch_plan(
        self,
        *,
        current_coach: User,
        plan_id: UUID,
        payload: WorkoutPlanPatch,
    ) -> WorkoutPlan:
        self._ensure_coach_role(current_coach)
        plan = self._get_owned_plan(coach_id=current_coach.id, plan_id=plan_id)
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise EmptyWorkoutPlanUpdateError("No workout plan fields were provided")
        if "exercises" in updates:
            updates["exercises"] = list(payload.exercises or [])

        return self.workout_plan_repository.update_plan_fields(plan=plan, updates=updates)

    def delete_plan(self, *, current_coach: User, plan_id: UUID) -> None:
        self._ensure_coach_role(current_coach)
        plan = self._get_owned_plan(coach_id=current_coach.id, plan_id=plan_id)
        self.workout_plan_repository.delete_plan(plan=plan)

    def assign_plan_to_client(
        self,
        *,
        current_coach: User,
        plan_id: UUID,
        client_id: UUID,
    ) -> WorkoutPlanAssignment:
        self._ensure_coach_role(current_coach)
        plan = self._get_owned_plan(coach_id=current_coach.id, plan_id=plan_id)

        if current_coach.id == client_id:
            raise InvalidWorkoutPlanAssignmentError("Coach cannot assign plan to self")

        client = self.user_repository.get_by_id(client_id)
        if client is None:
            raise WorkoutPlanClientNotFoundError("Client not found")

        is_managed_client = self.coach_client_repository.accepted_relationship_exists(
            coach_id=current_coach.id,
            client_id=client_id,
        )
        if not is_managed_client:
            raise WorkoutPlanClientNotManagedError("Client is not assigned to this coach")

        if self.workout_plan_repository.assignment_exists(plan_id=plan.id, client_id=client_id):
            raise WorkoutPlanAssignmentExistsError("Workout plan already assigned to this client")

        assignment = WorkoutPlanAssignment(
            plan_id=plan.id,
            client_id=client_id,
            assigned_by_coach_id=current_coach.id,
        )
        return self.workout_plan_repository.create_assignment(assignment=assignment)

    def list_viewable_plans(self, *, current_user: User) -> list[WorkoutPlan]:
        if current_user.role == UserRole.COACH:
            return self.workout_plan_repository.list_plans_by_coach(coach_id=current_user.id)
        return self.workout_plan_repository.list_plans_for_client(client_id=current_user.id)

    def get_viewable_plan(self, *, current_user: User, plan_id: UUID) -> WorkoutPlan:
        if current_user.role == UserRole.COACH:
            plan = self.workout_plan_repository.get_plan_by_id_for_coach(
                plan_id=plan_id,
                coach_id=current_user.id,
            )
        else:
            plan = self.workout_plan_repository.get_plan_for_client(
                plan_id=plan_id,
                client_id=current_user.id,
            )

        if plan is None:
            raise WorkoutPlanNotFoundError("Workout plan not found")
        return plan

    def _get_owned_plan(self, *, coach_id: UUID, plan_id: UUID) -> WorkoutPlan:
        plan = self.workout_plan_repository.get_plan_by_id_for_coach(
            plan_id=plan_id,
            coach_id=coach_id,
        )
        if plan is None:
            raise WorkoutPlanNotFoundError("Workout plan not found")
        return plan

    @staticmethod
    def _ensure_coach_role(current_user: User) -> None:
        if current_user.role != UserRole.COACH:
            raise WorkoutPlanServiceError("Coach role required")