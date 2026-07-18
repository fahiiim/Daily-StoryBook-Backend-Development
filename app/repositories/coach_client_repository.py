from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.coach_client import CoachClient
from app.models.user import User


class CoachClientRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def relationship_exists(self, *, coach_id: UUID, client_id: UUID) -> bool:
        statement = select(CoachClient.id).where(
            CoachClient.coach_id == coach_id,
            CoachClient.client_id == client_id,
        )
        return self.db.scalar(statement) is not None

    def add_relationship(
        self,
        *,
        coach_id: UUID,
        client_id: UUID,
        personalized_message: str | None,
        assign_initial_plan: bool,
    ) -> CoachClient:
        relationship = CoachClient(
            coach_id=coach_id,
            client_id=client_id,
            personalized_message=personalized_message,
            assign_initial_plan=assign_initial_plan,
        )
        self.db.add(relationship)
        self.db.commit()
        self.db.refresh(relationship)
        return relationship

    def remove_relationship(self, *, coach_id: UUID, client_id: UUID) -> bool:
        statement = delete(CoachClient).where(
            CoachClient.coach_id == coach_id,
            CoachClient.client_id == client_id,
        )
        result = self.db.execute(statement)
        self.db.commit()
        return bool(result.rowcount and result.rowcount > 0)

    def list_clients(self, *, coach_id: UUID) -> list[User]:
        statement = (
            select(User)
            .join(CoachClient, CoachClient.client_id == User.id)
            .where(CoachClient.coach_id == coach_id)
            .order_by(User.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def count_clients(self, *, coach_id: UUID) -> int:
        statement = select(func.count(CoachClient.id)).where(CoachClient.coach_id == coach_id)
        return int(self.db.scalar(statement) or 0)

    def get_client_for_coach(self, *, coach_id: UUID, client_id: UUID) -> User | None:
        statement = (
            select(User)
            .join(CoachClient, CoachClient.client_id == User.id)
            .where(
                CoachClient.coach_id == coach_id,
                CoachClient.client_id == client_id,
            )
        )
        return self.db.scalar(statement)