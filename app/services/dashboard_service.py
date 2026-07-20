from datetime import date
from uuid import UUID

from app.models.storybook import StorybookStatus
from app.models.user import User, UserRole
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.storybook_repository import StorybookRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_plan_repository import WorkoutPlanRepository
from app.schemas.dashboard import (
    ClientDashboardResponse,
    CoachActivity,
    CoachClientOverview,
    CoachDashboardResponse,
    CoachWeeklyCompletion,
    StorybookSummary,
)
from app.schemas.nutrition_plan import NutritionPlanRead
from app.schemas.routine import RoutineRead
from app.schemas.weekly_summary import WeeklySummaryRead
from app.schemas.workout_plan import WorkoutPlanRead
from app.services.weekly_summary_service import WeeklySummaryNotFoundError, WeeklySummaryService


class DashboardServiceError(Exception):
    pass


class DashboardAccessError(DashboardServiceError):
    pass


class DashboardNotFoundError(DashboardServiceError):
    pass


class DashboardService:
    def __init__(
        self,
        *,
        dashboard_repository: DashboardRepository,
        routine_repository: RoutineRepository,
        storybook_repository: StorybookRepository,
        workout_plan_repository: WorkoutPlanRepository,
        nutrition_plan_repository: NutritionPlanRepository,
        user_repository: UserRepository,
        coach_client_repository: CoachClientRepository,
        weekly_summary_service: WeeklySummaryService,
    ) -> None:
        self.dashboard_repository = dashboard_repository
        self.routine_repository = routine_repository
        self.storybook_repository = storybook_repository
        self.workout_plan_repository = workout_plan_repository
        self.nutrition_plan_repository = nutrition_plan_repository
        self.user_repository = user_repository
        self.coach_client_repository = coach_client_repository
        self.weekly_summary_service = weekly_summary_service

    def get_coach_dashboard(self, *, current_coach: User) -> CoachDashboardResponse:
        self._ensure_coach(current_coach)
        today = date.today()
        week_start, week_end = self._get_week_range(today)

        total_clients = self.dashboard_repository.count_clients(coach_id=current_coach.id)
        stories_today = self.dashboard_repository.count_storybooks_today(
            coach_id=current_coach.id,
            today=today,
        )
        pending_stories = self.dashboard_repository.count_pending_storybooks(coach_id=current_coach.id)

        total_routines, completed_routines = self.dashboard_repository.weekly_completion_stats(
            coach_id=current_coach.id,
            week_start=week_start,
            week_end=week_end,
        )
        completion_rate = (
            round((completed_routines / total_routines) * 100, 2) if total_routines else 0.0
        )

        recent_activities = self._build_recent_activities(current_coach=current_coach, limit=10)
        client_overview = self._build_client_overview(
            current_coach=current_coach,
            week_start=week_start,
            week_end=week_end,
        )

        return CoachDashboardResponse(
            total_clients=total_clients,
            stories_generated_today=stories_today,
            pending_stories=pending_stories,
            weekly_completion=CoachWeeklyCompletion(
                completed_routines=completed_routines,
                total_routines=total_routines,
                completion_rate=completion_rate,
            ),
            recent_activities=recent_activities,
            client_overview=client_overview,
        )

    def get_client_dashboard(
        self,
        *,
        current_coach: User,
        client_id: UUID,
    ) -> ClientDashboardResponse:
        self._ensure_coach(current_coach)
        target_user = self.user_repository.get_by_id(client_id)
        if target_user is None:
            raise DashboardNotFoundError("Client not found")

        if client_id != current_coach.id:
            if not self.coach_client_repository.accepted_relationship_exists(
                coach_id=current_coach.id,
                client_id=client_id,
            ):
                raise DashboardAccessError("Access to client dashboard is forbidden")

        today = date.today()
        routine = self.routine_repository.get_by_user_and_date(
            user_id=client_id,
            routine_date=today,
        )
        storybook = self.storybook_repository.get_by_user_and_date(
            user_id=client_id,
            story_date=today,
        )

        weekly_summary = None
        try:
            weekly_summary = self.weekly_summary_service.get_current_summary(
                current_user=current_coach,
                user_id=client_id,
            )
        except WeeklySummaryNotFoundError:
            weekly_summary = None

        workout_plans = self.workout_plan_repository.list_plans_for_client_by_coach(
            client_id=client_id,
            coach_id=current_coach.id,
        )
        nutrition_plans = self.nutrition_plan_repository.list_by_client_for_coach(
            client_id=client_id,
            coach_id=current_coach.id,
        )
        today_nutrition_plan = self.nutrition_plan_repository.get_by_coach_client_date(
            coach_id=current_coach.id,
            client_id=client_id,
            plan_date=today,
        )

        today_routine = None
        if routine is not None:
            today_routine = RoutineRead.model_validate(routine).model_copy(
                update={
                    "nutrition_plan": (
                        NutritionPlanRead.model_validate(today_nutrition_plan)
                        if today_nutrition_plan is not None
                        else None
                    ),
                    "goal_kcal": (
                        float(today_nutrition_plan.daily_calories)
                        if today_nutrition_plan is not None
                        and today_nutrition_plan.daily_calories is not None
                        else None
                    ),
                    "goal_protein": (
                        today_nutrition_plan.protein
                        if today_nutrition_plan is not None
                        else None
                    ),
                    "goal_carbs": (
                        today_nutrition_plan.carbs
                        if today_nutrition_plan is not None
                        else None
                    ),
                    "goal_fats": (
                        today_nutrition_plan.fat
                        if today_nutrition_plan is not None
                        else None
                    ),
                    "goal_fiber": (
                        today_nutrition_plan.fiber
                        if today_nutrition_plan is not None
                        else None
                    ),
                }
            )

        statistics = {
            "total_routines": len(
                self.routine_repository.list_by_user_between_dates(
                    user_id=client_id,
                    start_date=today,
                    end_date=today,
                )
            ),
            "workout_plan_count": len(workout_plans),
            "nutrition_plan_count": len(nutrition_plans),
        }
        if storybook is not None:
            statistics["storybook_status"] = storybook.status.value

        return ClientDashboardResponse(
            client_id=client_id,
            today_routine=today_routine,
            today_storybook=StorybookSummary.model_validate(storybook) if storybook else None,
            weekly_progress=WeeklySummaryRead.model_validate(weekly_summary)
            if weekly_summary
            else None,
            workout_plans=[WorkoutPlanRead.model_validate(plan) for plan in workout_plans],
            nutrition_plans=[NutritionPlanRead.model_validate(plan) for plan in nutrition_plans],
            subscription={},
            notifications=[],
            statistics=statistics,
        )

    @staticmethod
    def _get_week_range(today: date) -> tuple[date, date]:
        week_start = today - date.resolution * today.weekday()
        week_end = week_start + date.resolution * 6
        return week_start, week_end

    def _build_recent_activities(
        self,
        *,
        current_coach: User,
        limit: int,
    ) -> list[CoachActivity]:
        routine_rows = self.dashboard_repository.recent_routine_activities(
            coach_id=current_coach.id,
            limit=limit,
        )
        storybook_rows = self.dashboard_repository.recent_storybook_activities(
            coach_id=current_coach.id,
            limit=limit,
        )

        activities: list[CoachActivity] = []
        for created_at, routine_date, workout, completion_status, user_id, full_name in routine_rows:
            description = f"Routine {routine_date}"
            if workout:
                description += f" - {workout}"
            description += " (completed)" if completion_status else ""
            activities.append(
                CoachActivity(
                    activity_type="routine",
                    user_id=user_id,
                    user_name=full_name,
                    occurred_at=created_at,
                    description=description,
                )
            )

        for created_at, story_date, status, user_id, full_name in storybook_rows:
            description = f"Storybook {story_date} - {status.value}"
            activities.append(
                CoachActivity(
                    activity_type="storybook",
                    user_id=user_id,
                    user_name=full_name,
                    occurred_at=created_at,
                    description=description,
                )
            )

        activities.sort(key=lambda item: item.occurred_at, reverse=True)
        return activities[:limit]

    def _build_client_overview(
        self,
        *,
        current_coach: User,
        week_start: date,
        week_end: date,
    ) -> list[CoachClientOverview]:
        rows = self.dashboard_repository.client_overview(
            coach_id=current_coach.id,
            week_start=week_start,
            week_end=week_end,
        )

        overview: list[CoachClientOverview] = []
        for (
            user_id,
            full_name,
            email,
            last_routine_date,
            last_storybook_status,
            total_routines,
            completed_routines,
        ) in rows:
            completion_rate = None
            if total_routines:
                completion_rate = round((completed_routines / total_routines) * 100, 2)

            status_value = None
            if isinstance(last_storybook_status, StorybookStatus):
                status_value = last_storybook_status

            overview.append(
                CoachClientOverview(
                    user_id=user_id,
                    full_name=full_name,
                    email=email,
                    last_routine_date=last_routine_date,
                    last_storybook_status=status_value,
                    week_completion_rate=completion_rate,
                )
            )

        return overview

    @staticmethod
    def _ensure_coach(current_user: User) -> None:
        if current_user.role != UserRole.COACH:
            raise DashboardAccessError("Coach role required")
