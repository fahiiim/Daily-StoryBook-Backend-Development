import re
from uuid import UUID

from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, RegistrationInfoPatchRequest


class AuthServiceError(Exception):
    pass


class EmailAlreadyRegisteredError(AuthServiceError):
    pass


class UsernameAlreadyTakenError(AuthServiceError):
    pass


class InvalidCredentialsError(AuthServiceError):
    pass


class InactiveUserError(AuthServiceError):
    pass


class EmailNotVerifiedError(AuthServiceError):
    pass


class EmptyRegistrationInfoUpdateError(AuthServiceError):
    pass


class AuthService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    def register_user(self, payload: RegisterRequest) -> User:
        normalized_email = payload.email.strip().lower()

        existing_user = self.user_repository.get_by_email(normalized_email)
        if existing_user is not None:
            raise EmailAlreadyRegisteredError("Email already registered")

        generated_username = self._generate_username_from_email(normalized_email)

        return self.user_repository.create(
            username=generated_username,
            email=normalized_email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name.strip(),
            age=payload.age,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            occupation=payload.occupation,
            fitness_goal=payload.fitness_goal,
            wake_up_time=payload.wake_up_time,
            bed_time=payload.bed_time,
            height=payload.height,
            weight=payload.weight,
            target_weight=payload.target_weight,
            short_bio=payload.short_bio,
            fitness_motivation=payload.fitness_motivation,
            bio=None,
            profile_image=payload.profile_image,
            reference_image=payload.reference_image,
            use_reference_image=False,
            role=UserRole(payload.role),
            is_active=True,
            is_email_verified=False,
        )

    def _generate_username_from_email(self, email: str) -> str:
        local_part = email.split("@", 1)[0]
        base_username = re.sub(r"[^a-zA-Z0-9_]", "_", local_part).strip("_").lower()
        if len(base_username) < 3:
            base_username = "user"

        base_username = base_username[:50]
        username = base_username
        suffix = 1
        while self.user_repository.get_by_username(username) is not None:
            suffix_text = f"_{suffix}"
            username = f"{base_username[: 50 - len(suffix_text)]}{suffix_text}"
            suffix += 1

        return username

    def login_user(self, payload: LoginRequest) -> str:
        normalized_email = payload.email.strip().lower()

        user = self.user_repository.get_by_email(normalized_email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password")

        if not user.is_active:
            raise InactiveUserError("Inactive user account")

        if not user.is_email_verified:
            raise EmailNotVerifiedError("Email is not verified")

        return create_access_token(subject=str(user.id))

    def update_registration_info(self, *, current_user: User, payload: RegistrationInfoPatchRequest) -> User:
        user = self.user_repository.get_by_id(current_user.id)
        if user is None:
            raise InvalidCredentialsError("User not found")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise EmptyRegistrationInfoUpdateError("No registration information fields were provided")

        if "full_name" in updates and isinstance(updates["full_name"], str):
            updates["full_name"] = updates["full_name"].strip()

        return self.user_repository.update_fields(user=user, updates=updates)

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