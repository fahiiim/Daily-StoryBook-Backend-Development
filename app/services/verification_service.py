from datetime import datetime, timedelta, timezone
from secrets import randbelow
from uuid import UUID

from app.models.verification_code import VerificationCode, VerificationCodePurpose
from app.repositories.verification_code_repository import VerificationCodeRepository


class VerificationServiceError(Exception):
    pass


class InvalidVerificationCodeError(VerificationServiceError):
    pass


class ExpiredVerificationCodeError(VerificationServiceError):
    pass


class VerificationService:
    CODE_EXPIRY_MINUTES = 10

    def __init__(self, verification_code_repository: VerificationCodeRepository) -> None:
        self.verification_code_repository = verification_code_repository

    def generate_code(self, *, user_id: UUID, purpose: VerificationCodePurpose) -> str:
        now = datetime.now(tz=timezone.utc)
        code = f"{randbelow(1_000_000):06d}"

        self.verification_code_repository.invalidate_unconsumed_codes(
            user_id=user_id,
            purpose=purpose,
            consumed_at=now,
            commit=False,
        )

        verification_code = VerificationCode(
            user_id=user_id,
            code_hash=code,
            purpose=purpose,
            expires_at=now + timedelta(minutes=self.CODE_EXPIRY_MINUTES),
            consumed_at=None,
        )
        self.verification_code_repository.create(verification_code=verification_code, commit=False)
        self.verification_code_repository.db.commit()
        return code

    def verify_code(
        self,
        *,
        user_id: UUID,
        purpose: VerificationCodePurpose,
        submitted_code: str,
    ) -> None:
        verification_code = self.verification_code_repository.get_latest_by_user_and_purpose(
            user_id=user_id,
            purpose=purpose,
        )
        if verification_code is None:
            raise InvalidVerificationCodeError("Invalid verification code")

        if verification_code.consumed_at is not None:
            raise InvalidVerificationCodeError("Verification code has already been used")

        now = datetime.now(tz=timezone.utc)
        expires_at = self._as_aware_utc(verification_code.expires_at)
        if expires_at <= now:
            raise ExpiredVerificationCodeError("Verification code has expired")

        if submitted_code != verification_code.code_hash:
            raise InvalidVerificationCodeError("Invalid verification code")

        self.verification_code_repository.mark_consumed(
            verification_code=verification_code,
            consumed_at=now,
            commit=True,
        )

    @staticmethod
    def _as_aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
