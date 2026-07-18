from uuid import UUID

from app.models.coach_client import CoachClient
from app.models.user import User, UserRole
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.user_repository import UserRepository


class CoachClientServiceError(Exception):
    pass


class CoachRoleRequiredError(CoachClientServiceError):
    pass


class CoachClientRelationshipExistsError(CoachClientServiceError):
    pass


class CoachClientRelationshipNotFoundError(CoachClientServiceError):
    pass


class CoachClientNotFoundError(CoachClientServiceError):
    pass


class InvalidCoachClientAssignmentError(CoachClientServiceError):
    pass


class CoachClientService:
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        coach_client_repository: CoachClientRepository,
    ) -> None:
        self.user_repository = user_repository
        self.coach_client_repository = coach_client_repository

    def add_client(self, *, current_coach: User, client_email: str) -> CoachClient:
        self._ensure_coach_role(current_coach)

        normalized_email = client_email.strip().lower()
        client = self.user_repository.get_by_email(normalized_email)
        if client is None:
            raise CoachClientNotFoundError("Client not found")

        client_id = client.id

        if current_coach.id == client_id:
            raise InvalidCoachClientAssignmentError("Coach cannot add self as client")

        if self.coach_client_repository.relationship_exists(
            coach_id=current_coach.id,
            client_id=client_id,
        ):
            raise CoachClientRelationshipExistsError("Client already assigned to coach")

        return self.coach_client_repository.add_relationship(
            coach_id=current_coach.id,
            client_id=client_id,
        )

    def remove_client(self, *, current_coach: User, client_id: UUID) -> None:
        self._ensure_coach_role(current_coach)

        removed = self.coach_client_repository.remove_relationship(
            coach_id=current_coach.id,
            client_id=client_id,
        )
        if not removed:
            raise CoachClientRelationshipNotFoundError("Coach-client relationship not found")

    def list_clients(self, *, current_coach: User) -> list[User]:
        self._ensure_coach_role(current_coach)
        return self.coach_client_repository.list_clients(coach_id=current_coach.id)

    def get_client_profile(self, *, current_coach: User, client_id: UUID) -> User:
        self._ensure_coach_role(current_coach)

        client = self.coach_client_repository.get_client_for_coach(
            coach_id=current_coach.id,
            client_id=client_id,
        )
        if client is None:
            raise CoachClientRelationshipNotFoundError("Coach-client relationship not found")

        return client

    @staticmethod
    def _ensure_coach_role(current_user: User) -> None:
        if current_user.role != UserRole.COACH:
            raise CoachRoleRequiredError("Coach role required")