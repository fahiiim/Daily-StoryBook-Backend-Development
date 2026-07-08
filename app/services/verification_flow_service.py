from app.core.security import hash_password
from app.models.user import User
from app.models.verification_code import VerificationCodePurpose
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService
from app.services.verification_service import (
    InvalidVerificationCodeError,
    VerificationService,
)


class VerificationFlowServiceError(Exception):
    pass


class VerificationUserNotFoundError(VerificationFlowServiceError):
    pass


class VerificationFlowService:
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        verification_service: VerificationService,
        email_service: EmailService,
    ) -> None:
        self.user_repository = user_repository
        self.verification_service = verification_service
        self.email_service = email_service

    def send_email_verification(self, *, current_user: User) -> str:
        user = self.user_repository.get_by_id(current_user.id)
        if user is None:
            raise VerificationUserNotFoundError("User not found")

        code = self.verification_service.generate_code(
            user_id=user.id,
            purpose=VerificationCodePurpose.EMAIL_VERIFICATION,
        )
        self.email_service.send_email(
            to=user.email,
            subject="Verify your email",
            body=f"Your verification code is: {code}",
        )
        return code

    def verify_email(self, *, current_user: User, code: str) -> User:
        user = self.user_repository.get_by_id(current_user.id)
        if user is None:
            raise VerificationUserNotFoundError("User not found")

        self.verification_service.verify_code(
            user_id=user.id,
            purpose=VerificationCodePurpose.EMAIL_VERIFICATION,
            submitted_code=code,
        )
        return self.user_repository.update_fields(user=user, updates={"is_email_verified": True})

    def request_password_reset(self, *, email: str) -> str | None:
        normalized_email = email.strip().lower()
        user = self.user_repository.get_by_email(normalized_email)
        if user is None:
            return None

        code = self.verification_service.generate_code(
            user_id=user.id,
            purpose=VerificationCodePurpose.PASSWORD_RESET,
        )
        self.email_service.send_email(
            to=user.email,
            subject="Reset your password",
            body=f"Your password reset code is: {code}",
        )
        return code

    def reset_password(self, *, email: str, code: str, new_password: str) -> None:
        normalized_email = email.strip().lower()
        user = self.user_repository.get_by_email(normalized_email)
        if user is None:
            raise InvalidVerificationCodeError("Invalid email or verification code")

        self.verification_service.verify_code(
            user_id=user.id,
            purpose=VerificationCodePurpose.PASSWORD_RESET,
            submitted_code=code,
        )
        self.user_repository.update_fields(
            user=user,
            updates={"hashed_password": hash_password(new_password)},
        )
