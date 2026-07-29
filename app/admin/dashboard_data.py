from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import Integer, String, func, or_, select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.routine import Routine
from app.models.routine_macro_log import RoutineMacroLog
from app.models.storybook import Storybook, StorybookStatus, StoryPage
from app.models.user import User, UserRole
from app.models.workout_plan import WorkoutPlanCompletionEvent
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.daily_goal_repository import DailyGoalCompletionRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_macro_log_repository import RoutineMacroLogRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workout_plan_repository import WorkoutPlanCompletionRepository
from app.schemas.weekly_summary import (
    WeeklyGoalDayRead,
    WeeklyMealDayRead,
    WeeklyWorkoutDayRead,
)
from app.services.weekly_summary_service import WeeklySummaryService


class AdminDashboardNotFoundError(Exception):
    pass


def initials(value: str | None) -> str:
    parts = [part for part in (value or "").strip().split() if part]
    if not parts:
        return "DS"
    return "".join(part[0].upper() for part in parts[:2])


def relative_time(value: datetime | None) -> str:
    if value is None:
        return "No activity yet"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    seconds = max(0, int((datetime.now(tz=UTC) - value).total_seconds()))
    if seconds < 60:
        return "Just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago"
    days = hours // 24
    if days == 1:
        return "Yesterday"
    if days < 30:
        return f"{days} days ago"
    return value.strftime("%d %b %Y")


class AdminDashboardData:
    def __init__(self, db: Session) -> None:
        self.db = db

    def navigation(self) -> dict[str, int]:
        unread = self.db.scalar(
            select(func.count(Notification.id)).where(Notification.is_read.is_(False))
        )
        return {"unread_notifications": int(unread or 0)}

    def overview(self, *, days: int) -> dict[str, object]:
        today = date.today()
        range_start = today - timedelta(days=max(days - 1, 0))
        week_start = today - timedelta(days=today.weekday())

        active_clients = int(
            self.db.scalar(
                select(func.count(User.id)).where(
                    User.role == UserRole.SELF,
                    User.is_active.is_(True),
                )
            )
            or 0
        )
        new_clients = int(
            self.db.scalar(
                select(func.count(User.id)).where(
                    User.role == UserRole.SELF,
                    User.is_active.is_(True),
                    User.created_at >= datetime.now(tz=UTC) - timedelta(days=30),
                )
            )
            or 0
        )

        routine_rows = list(
            self.db.execute(
                select(Routine.date, Routine.completion_status, func.count(Routine.id))
                .join(User, User.id == Routine.user_id)
                .where(
                    User.role == UserRole.SELF,
                    User.is_active.is_(True),
                    Routine.date >= week_start,
                    Routine.date <= today,
                )
                .group_by(Routine.date, Routine.completion_status)
            ).all()
        )
        chart_map = {
            week_start + timedelta(days=offset): {"completed": 0, "missed": 0}
            for offset in range(7)
        }
        for routine_date, completed, count in routine_rows:
            bucket = chart_map.get(routine_date)
            if bucket is not None:
                bucket["completed" if completed else "missed"] += int(count)

        weekly_completed = sum(day["completed"] for day in chart_map.values())
        weekly_missed = sum(day["missed"] for day in chart_map.values())
        weekly_total = weekly_completed + weekly_missed
        completion_rate = round(weekly_completed / weekly_total * 100) if weekly_total else 0

        stories_generated = int(
            self.db.scalar(
                select(func.count(Storybook.id)).where(
                    Storybook.status == StorybookStatus.COMPLETED,
                    Storybook.date >= range_start,
                    Storybook.date <= today,
                )
            )
            or 0
        )
        pending_reviews = int(
            self.db.scalar(
                select(func.count(Storybook.id)).where(
                    Storybook.status.in_([StorybookStatus.FAILED, StorybookStatus.PENDING])
                )
            )
            or 0
        )

        chart_totals = [
            (point_date, counts["completed"], counts["missed"])
            for point_date, counts in chart_map.items()
        ]
        chart_max = (
            max(
                (completed + missed for _, completed, missed in chart_totals),
                default=0,
            )
            or 1
        )
        chart: list[dict[str, object]] = [
            {
                "day": point_date.strftime("%a"),
                "date": point_date,
                "completed": completed,
                "missed": missed,
                "total": completed + missed,
                "completed_height": round(completed / chart_max * 150),
                "missed_height": round(missed / chart_max * 150),
            }
            for point_date, completed, missed in chart_totals
        ]

        return {
            "active_clients": active_clients,
            "new_clients": new_clients,
            "weekly_tasks_completed": weekly_completed,
            "completion_rate": completion_rate,
            "stories_generated": stories_generated,
            "pending_reviews": pending_reviews,
            "chart": chart,
            "recent_activity": self._recent_activity(limit=5),
        }

    def list_clients(
        self,
        *,
        search: str | None,
        status_filter: str | None,
        days: int,
    ) -> list[dict[str, object]]:
        today = date.today()
        start_date = today - timedelta(days=max(days - 1, 0))
        statement = select(User).where(User.role == UserRole.SELF)
        if search:
            pattern = f"%{search.strip().lower()}%"
            statement = statement.where(
                or_(
                    func.lower(User.full_name).like(pattern),
                    func.lower(User.email).like(pattern),
                    func.lower(User.fitness_goal).like(pattern),
                )
            )
        users = list(self.db.scalars(statement.order_by(User.created_at.desc())))
        user_ids = [user.id for user in users]
        if not user_ids:
            return []

        adherence_rows = self.db.execute(
            select(
                Routine.user_id,
                func.count(Routine.id),
                func.sum(func.cast(Routine.completion_status, Integer)),
            )
            .where(
                Routine.user_id.in_(user_ids),
                Routine.date >= start_date,
                Routine.date <= today,
            )
            .group_by(Routine.user_id)
        ).all()
        adherence = {
            user_id: (int(total or 0), int(completed or 0))
            for user_id, total, completed in adherence_rows
        }
        last_activity = self._last_activity_by_user(user_ids)

        rows: list[dict[str, object]] = []
        for user in users:
            total, completed = adherence.get(user.id, (0, 0))
            percentage = round(completed / total * 100) if total else None
            if not user.is_active:
                status = "Inactive"
            elif percentage is not None and percentage < 50:
                status = "At risk"
            elif total == 0:
                status = "Needs setup"
            else:
                status = "Active"

            normalized_filter = (status_filter or "").strip().lower()
            if normalized_filter and status.lower().replace(" ", "-") != normalized_filter:
                continue

            rows.append(
                {
                    "id": user.id,
                    "name": user.full_name,
                    "email": user.email,
                    "initials": initials(user.full_name),
                    "profile_image": self._usable_image(user.profile_image),
                    "goal": self._display_goal(user.fitness_goal),
                    "adherence": percentage,
                    "last_active": relative_time(last_activity.get(user.id, user.updated_at)),
                    "status": status,
                    "is_active": user.is_active,
                }
            )
        return rows

    def get_client(self, *, client_id: UUID, days: int = 7) -> dict[str, object]:
        user = self.db.scalar(select(User).where(User.id == client_id, User.role == UserRole.SELF))
        if user is None:
            raise AdminDashboardNotFoundError("Client not found")

        client_rows = self.list_clients(search=user.email, status_filter=None, days=days)
        summary_row = next(
            (row for row in client_rows if row["id"] == user.id),
            {
                "adherence": None,
                "status": "Active" if user.is_active else "Inactive",
                "last_active": relative_time(user.updated_at),
            },
        )
        workout_count = int(
            self.db.scalar(
                select(func.count(WorkoutPlanCompletionEvent.id)).where(
                    WorkoutPlanCompletionEvent.client_id == user.id,
                    WorkoutPlanCompletionEvent.completed.is_(True),
                )
            )
            or 0
        )
        story_count = int(
            self.db.scalar(select(func.count(Storybook.id)).where(Storybook.user_id == user.id))
            or 0
        )
        return {
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
            "initials": initials(user.full_name),
            "profile_image": self._usable_image(user.profile_image),
            "goal": self._display_goal(user.fitness_goal),
            "status": summary_row["status"],
            "adherence": summary_row["adherence"] or 0,
            "last_active": summary_row["last_active"],
            "joined": user.created_at.strftime("%B %Y"),
            "day_streak": self._completion_streak(user.id),
            "goal_gap": self._goal_gap(user.weight, user.target_weight),
            "workouts": workout_count,
            "storybooks": story_count,
            "recent_activity": self._recent_activity(limit=5, user_id=user.id),
        }

    def weekly_overview(self, *, client_id: UUID) -> dict[str, object]:
        client = self.db.scalar(
            select(User).where(User.id == client_id, User.role == UserRole.SELF)
        )
        if client is None:
            raise AdminDashboardNotFoundError("Client not found")

        service = self._weekly_summary_service()
        analytics = service.get_current_week_analytics(current_user=client)
        workouts = service.get_current_week_workouts(current_user=client)
        meals = service.get_current_week_meals(current_user=client)
        goals = service.get_current_week_goals(current_user=client)
        routines = {
            routine.date: routine
            for routine in self.db.scalars(
                select(Routine).where(
                    Routine.user_id == client.id,
                    Routine.date >= analytics.week_start,
                    Routine.date <= analytics.week_end,
                )
            )
        }

        days: list[dict[str, object]] = []
        for point, workout, meal, goal in zip(
            analytics.daily_points,
            workouts.days,
            meals.days,
            goals.days,
            strict=True,
        ):
            routine = routines.get(point.date)
            instruction = next(
                (item.instruction for item in workout.items if item.instruction),
                routine.workout if routine else None,
            )
            applicable = workout.applicable or meal.applicable or goal.applicable
            if point.is_future:
                day_status = "Upcoming"
            elif not applicable and routine is None:
                day_status = "Rest"
            elif (point.combined_score or 0) >= 75 or (
                routine is not None and routine.completion_status
            ):
                day_status = "Completed"
            else:
                day_status = "Missed"
            days.append(
                {
                    "day": point.date.strftime("%a"),
                    "date": point.date,
                    "title": instruction or "Daily wellness check-in",
                    "note": (
                        routine.notes
                        if routine and routine.notes
                        else self._day_note(workout, meal, goal)
                    ),
                    "status": day_status,
                    "score": point.combined_score,
                }
            )

        calories = sum(
            float(routine.meals_kcal or 0)
            for routine in routines.values()
            if routine.date <= analytics.as_of_date
        )
        completed_workouts = sum(point.workout_completed for point in analytics.daily_points)
        weekly_percentage = analytics.weekly_progress_percentage
        return {
            "client": {
                "id": client.id,
                "name": client.full_name,
                "initials": initials(client.full_name),
            },
            "week_start": analytics.week_start,
            "week_end": analytics.week_end,
            "week_label": (
                f"{analytics.week_start.strftime('%d %b')} - {analytics.week_end.strftime('%d %b')}"
            ),
            "weekly_percentage": round(weekly_percentage or 0),
            "coverage": analytics.coverage,
            "days": days,
            "estimated_active_minutes": completed_workouts * 30,
            "calories": round(calories),
            "goal_status": (
                "On track"
                if weekly_percentage is not None and weekly_percentage >= 70
                else "Needs attention"
            ),
        }

    def list_storybooks(
        self,
        *,
        search: str | None,
        status_filter: str | None,
        days: int,
    ) -> list[dict[str, object]]:
        start_date = date.today() - timedelta(days=max(days - 1, 0))
        cover_subquery = (
            select(StoryPage.image_url)
            .where(StoryPage.storybook_id == Storybook.id)
            .order_by(StoryPage.page_number.asc())
            .limit(1)
            .scalar_subquery()
        )
        page_count_subquery = (
            select(func.count(StoryPage.id))
            .where(StoryPage.storybook_id == Storybook.id)
            .correlate(Storybook)
            .scalar_subquery()
        )
        statement = (
            select(Storybook, User, cover_subquery, page_count_subquery)
            .join(User, User.id == Storybook.user_id)
            .where(Storybook.date >= start_date)
        )
        if search:
            pattern = f"%{search.strip().lower()}%"
            statement = statement.where(
                or_(
                    func.lower(User.full_name).like(pattern),
                    func.lower(User.email).like(pattern),
                    func.lower(func.cast(Storybook.status, String)).like(pattern),
                )
            )
        if status_filter:
            try:
                statement = statement.where(
                    Storybook.status == StorybookStatus(status_filter.upper())
                )
            except ValueError:
                pass

        records = self.db.execute(statement.order_by(Storybook.created_at.desc()).limit(100)).all()
        return [
            {
                "id": storybook.id,
                "user_id": user.id,
                "client_name": user.full_name,
                "initials": initials(user.full_name),
                "date": storybook.date,
                "date_label": storybook.date.strftime("%A, %d %b"),
                "status": storybook.status.value,
                "cover_image": self._usable_image(cover),
                "page_count": int(page_count or 0),
                "pdf_url": storybook.pdf_url,
                "can_retry": storybook.status in {StorybookStatus.FAILED, StorybookStatus.PENDING},
            }
            for storybook, user, cover, page_count in records
        ]

    def bulk_candidates(self) -> list[dict[str, object]]:
        users = list(
            self.db.scalars(
                select(User)
                .where(User.role == UserRole.SELF, User.is_active.is_(True))
                .order_by(User.full_name.asc())
            )
        )
        plan_repository = NutritionPlanRepository(self.db)
        today = date.today()
        candidates: list[dict[str, object]] = []
        for user in users:
            plan = plan_repository.get_active_by_client_date(
                client_id=user.id,
                plan_date=today,
            )
            routine = self.db.scalar(
                select(Routine).where(Routine.user_id == user.id, Routine.date == today)
            )
            has_image = any(
                self._usable_image(value) for value in (user.reference_image, user.profile_image)
            )
            reasons = []
            if plan is None:
                reasons.append("Missing active plan")
            if routine is None:
                reasons.append("Missing daily notes")
            if not has_image:
                reasons.append("Missing profile image")
            candidates.append(
                {
                    "id": user.id,
                    "name": user.full_name,
                    "initials": initials(user.full_name),
                    "goal": self._display_goal(user.fitness_goal),
                    "ready": not reasons,
                    "reason": reasons[0] if reasons else "Ready",
                }
            )
        return candidates

    def export_clients(self) -> list[list[str]]:
        rows = self.list_clients(search=None, status_filter=None, days=7)
        return [
            [
                str(row["id"]),
                str(row["name"]),
                str(row["email"]),
                str(row["goal"]),
                str(row["adherence"] if row["adherence"] is not None else ""),
                str(row["status"]),
                str(row["last_active"]),
            ]
            for row in rows
        ]

    def export_storybooks(self) -> list[list[str]]:
        rows = self.list_storybooks(search=None, status_filter=None, days=3650)
        return [
            [
                str(row["id"]),
                str(row["client_name"]),
                str(row["date"]),
                str(row["status"]),
                str(row["page_count"]),
                str(row["pdf_url"] or ""),
            ]
            for row in rows
        ]

    def _last_activity_by_user(self, user_ids: list[UUID]) -> dict[UUID, datetime]:
        result: dict[UUID, datetime] = {}
        sources = [
            self.db.execute(
                select(Routine.user_id, func.max(Routine.updated_at))
                .where(Routine.user_id.in_(user_ids))
                .group_by(Routine.user_id)
            ).all(),
            self.db.execute(
                select(Storybook.user_id, func.max(Storybook.updated_at))
                .where(Storybook.user_id.in_(user_ids))
                .group_by(Storybook.user_id)
            ).all(),
            self.db.execute(
                select(RoutineMacroLog.user_id, func.max(RoutineMacroLog.logged_at))
                .where(RoutineMacroLog.user_id.in_(user_ids))
                .group_by(RoutineMacroLog.user_id)
            ).all(),
        ]
        for rows in sources:
            for user_id, timestamp in rows:
                if timestamp is not None and (user_id not in result or timestamp > result[user_id]):
                    result[user_id] = timestamp
        return result

    def _recent_activity(
        self,
        *,
        limit: int,
        user_id: UUID | None = None,
    ) -> list[dict[str, object]]:
        routine_statement = select(Routine, User).join(User, User.id == Routine.user_id)
        story_statement = select(Storybook, User).join(User, User.id == Storybook.user_id)
        if user_id is not None:
            routine_statement = routine_statement.where(Routine.user_id == user_id)
            story_statement = story_statement.where(Storybook.user_id == user_id)

        routines = self.db.execute(
            routine_statement.order_by(Routine.updated_at.desc()).limit(limit)
        ).all()
        stories = self.db.execute(
            story_statement.order_by(Storybook.updated_at.desc()).limit(limit)
        ).all()
        activity: list[dict[str, object]] = []
        for routine, user in routines:
            activity.append(
                {
                    "user_id": user.id,
                    "name": user.full_name,
                    "initials": initials(user.full_name),
                    "profile_image": self._usable_image(user.profile_image),
                    "message": (
                        f"Completed {routine.workout or 'daily routine'}"
                        if routine.completion_status
                        else f"Updated {routine.workout or 'daily routine'}"
                    ),
                    "occurred_at": routine.updated_at,
                    "time": relative_time(routine.updated_at),
                    "kind": "routine",
                    "score": None,
                }
            )
        for storybook, user in stories:
            activity.append(
                {
                    "user_id": user.id,
                    "name": user.full_name,
                    "initials": initials(user.full_name),
                    "profile_image": self._usable_image(user.profile_image),
                    "message": (
                        "Generated a Daily Storybook"
                        if storybook.status == StorybookStatus.COMPLETED
                        else f"Storybook is {storybook.status.value.lower()}"
                    ),
                    "occurred_at": storybook.updated_at,
                    "time": relative_time(storybook.updated_at),
                    "kind": "storybook",
                    "score": None,
                }
            )
        activity.sort(
            key=lambda item: cast(datetime, item["occurred_at"]),
            reverse=True,
        )
        return activity[:limit]

    def _completion_streak(self, user_id: UUID) -> int:
        completed_dates = set(
            self.db.scalars(
                select(Routine.date).where(
                    Routine.user_id == user_id,
                    Routine.completion_status.is_(True),
                )
            )
        )
        cursor = date.today()
        if cursor not in completed_dates:
            cursor -= timedelta(days=1)
        streak = 0
        while cursor in completed_dates:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    def _weekly_summary_service(self) -> WeeklySummaryService:
        return WeeklySummaryService(
            routine_repository=RoutineRepository(self.db),
            routine_macro_log_repository=RoutineMacroLogRepository(self.db),
            workout_plan_repository=WorkoutPlanCompletionRepository(self.db),
            daily_goal_repository=DailyGoalCompletionRepository(self.db),
            nutrition_plan_repository=NutritionPlanRepository(self.db),
            user_repository=UserRepository(self.db),
            coach_client_repository=CoachClientRepository(self.db),
        )

    @staticmethod
    def _display_goal(value: str | None) -> str:
        normalized = (value or "").strip().replace("_", " ")
        if not normalized or normalized.lower() == "string":
            return "General fitness"
        return normalized.title()

    @staticmethod
    def _goal_gap(weight: float | None, target_weight: float | None) -> float | None:
        if weight is None or target_weight is None:
            return None
        return round(abs(weight - target_weight), 1)

    @staticmethod
    def _usable_image(value: str | None) -> str | None:
        normalized = (value or "").strip()
        if not normalized or normalized.lower() in {"string", "null", "none"}:
            return None
        if normalized.startswith(("http://", "https://", "/", "data:image/")):
            return normalized
        return None

    @staticmethod
    def _day_note(
        workout: WeeklyWorkoutDayRead,
        meal: WeeklyMealDayRead,
        goal: WeeklyGoalDayRead,
    ) -> str:
        if workout.assigned_count:
            return f"{workout.completed_count} of {workout.assigned_count} workout tasks complete"
        if goal.assigned_count:
            return f"{goal.completed_count} of {goal.assigned_count} daily goals complete"
        if meal.applicable:
            return f"Nutrition score {round(meal.meal_score or 0)}%"
        return "No routine assigned"
