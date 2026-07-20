from datetime import date
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.coach_client import CoachClient, CoachClientStatus
from app.models.routine import Routine
from app.models.storybook import Storybook, StorybookStatus
from app.models.user import User


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def count_clients(self, *, coach_id: UUID) -> int:
        statement = select(func.count(CoachClient.id)).where(
            CoachClient.coach_id == coach_id,
            CoachClient.status == CoachClientStatus.ACCEPTED,
        )
        return int(self.db.scalar(statement) or 0)

    def count_storybooks_today(self, *, coach_id: UUID, today: date) -> int:
        statement = (
            select(func.count(Storybook.id))
            .select_from(Storybook)
            .join(CoachClient, Storybook.user_id == CoachClient.client_id)
            .where(
                CoachClient.coach_id == coach_id,
                CoachClient.status == CoachClientStatus.ACCEPTED,
                Storybook.date == today,
            )
        )
        return int(self.db.scalar(statement) or 0)

    def count_pending_storybooks(self, *, coach_id: UUID) -> int:
        statement = (
            select(func.count(Storybook.id))
            .select_from(Storybook)
            .join(CoachClient, Storybook.user_id == CoachClient.client_id)
            .where(
                CoachClient.coach_id == coach_id,
                CoachClient.status == CoachClientStatus.ACCEPTED,
                Storybook.status.in_([StorybookStatus.PENDING, StorybookStatus.PROCESSING]),
            )
        )
        return int(self.db.scalar(statement) or 0)

    def weekly_completion_stats(
        self,
        *,
        coach_id: UUID,
        week_start: date,
        week_end: date,
    ) -> tuple[int, int]:
        completed_case = case((Routine.completion_status.is_(True), 1), else_=0)
        statement = (
            select(
                func.count(Routine.id),
                func.coalesce(func.sum(completed_case), 0),
            )
            .select_from(Routine)
            .join(CoachClient, Routine.user_id == CoachClient.client_id)
            .where(
                CoachClient.coach_id == coach_id,
                CoachClient.status == CoachClientStatus.ACCEPTED,
                Routine.date >= week_start,
                Routine.date <= week_end,
            )
        )
        total, completed = self.db.execute(statement).one()
        return int(total or 0), int(completed or 0)

    def recent_routine_activities(self, *, coach_id: UUID, limit: int) -> list[tuple]:
        statement = (
            select(
                Routine.created_at,
                Routine.date,
                Routine.workout,
                Routine.completion_status,
                User.id,
                User.full_name,
            )
            .select_from(Routine)
            .join(User, Routine.user_id == User.id)
            .join(CoachClient, CoachClient.client_id == User.id)
            .where(
                CoachClient.coach_id == coach_id,
                CoachClient.status == CoachClientStatus.ACCEPTED,
            )
            .order_by(Routine.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(statement).all())

    def recent_storybook_activities(self, *, coach_id: UUID, limit: int) -> list[tuple]:
        statement = (
            select(
                Storybook.created_at,
                Storybook.date,
                Storybook.status,
                User.id,
                User.full_name,
            )
            .select_from(Storybook)
            .join(User, Storybook.user_id == User.id)
            .join(CoachClient, CoachClient.client_id == User.id)
            .where(
                CoachClient.coach_id == coach_id,
                CoachClient.status == CoachClientStatus.ACCEPTED,
            )
            .order_by(Storybook.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(statement).all())

    def client_overview(
        self,
        *,
        coach_id: UUID,
        week_start: date,
        week_end: date,
    ) -> list[tuple]:
        last_routine_subq = (
            select(
                Routine.user_id.label("user_id"),
                func.max(Routine.date).label("last_routine_date"),
            )
            .group_by(Routine.user_id)
            .subquery()
        )

        last_storybook_subq = (
            select(
                Storybook.user_id.label("user_id"),
                func.max(Storybook.created_at).label("last_storybook_created"),
            )
            .group_by(Storybook.user_id)
            .subquery()
        )

        latest_storybook_subq = (
            select(
                Storybook.user_id.label("user_id"),
                Storybook.status.label("last_storybook_status"),
            )
            .join(
                last_storybook_subq,
                (Storybook.user_id == last_storybook_subq.c.user_id)
                & (Storybook.created_at == last_storybook_subq.c.last_storybook_created),
            )
            .subquery()
        )

        completed_case = case((Routine.completion_status.is_(True), 1), else_=0)
        week_stats_subq = (
            select(
                Routine.user_id.label("user_id"),
                func.count(Routine.id).label("total_routines"),
                func.coalesce(func.sum(completed_case), 0).label("completed_routines"),
            )
            .where(Routine.date >= week_start, Routine.date <= week_end)
            .group_by(Routine.user_id)
            .subquery()
        )

        statement = (
            select(
                User.id,
                User.full_name,
                User.email,
                last_routine_subq.c.last_routine_date,
                latest_storybook_subq.c.last_storybook_status,
                week_stats_subq.c.total_routines,
                week_stats_subq.c.completed_routines,
            )
            .select_from(CoachClient)
            .join(User, CoachClient.client_id == User.id)
            .outerjoin(last_routine_subq, last_routine_subq.c.user_id == User.id)
            .outerjoin(latest_storybook_subq, latest_storybook_subq.c.user_id == User.id)
            .outerjoin(week_stats_subq, week_stats_subq.c.user_id == User.id)
            .where(
                CoachClient.coach_id == coach_id,
                CoachClient.status == CoachClientStatus.ACCEPTED,
            )
            .order_by(User.created_at.desc())
        )
        return list(self.db.execute(statement).all())
