from uuid import UUID

from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest


class AuthServiceError(Exception):
    pass


class EmailAlreadyRegisteredError(AuthServiceError):
    pass


class InvalidCredentialsError(AuthServiceError):
    pass


class InactiveUserError(AuthServiceError):
    pass


class AuthService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    def register_user(self, payload: RegisterRequest) -> User:
        normalized_email = payload.email.strip().lower()

        existing_user = self.user_repository.get_by_email(normalized_email)
        if existing_user is not None:
            raise EmailAlreadyRegisteredError("Email already registered")

        return self.user_repository.create(
            email=normalized_email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name.strip(),
            age=payload.age,
            gender=payload.gender,
            occupation=payload.occupation,
            fitness_goal=payload.fitness_goal,
            profile_image=payload.profile_image,
            reference_image=payload.reference_image,
            role=payload.role,
            is_active=payload.is_active,
        )

    def login_user(self, payload: LoginRequest) -> str:
        normalized_email = payload.email.strip().lower()

        user = self.user_repository.get_by_email(normalized_email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password")

        if not user.is_active:
            raise InactiveUserError("Inactive user account")

        return create_access_token(subject=str(user.id))

    def get_current_user(self, token: str) -> User:
        try:
            payload = decode_token(token)
        except ValueError as exc:
            raise InvalidCredentialsError("Invalid token") from exc

        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise InvalidCredentialsError("Invalid token payload")

        try:
            user_id = UUID(subject)
        except ValueError as exc:
            raise InvalidCredentialsError("Invalid token subject") from exc

        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError("User not found")

        if not user.is_active:
            raise InactiveUserError("Inactive user account")

        return user