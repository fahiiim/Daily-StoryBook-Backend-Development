from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.verification_code import VerificationCode, VerificationCodePurpose


class VerificationCodeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, verification_code: VerificationCode, commit: bool = True) -> VerificationCode:
        self.db.add(verification_code)
        if commit:
            self.db.commit()
            self.db.refresh(verification_code)
        else:
            self.db.flush()
            self.db.refresh(verification_code)
        return verification_code

    def invalidate_unconsumed_codes(
        self,
        *,
        user_id: UUID,
        purpose: VerificationCodePurpose,
        consumed_at: datetime,
        commit: bool = True,
    ) -> int:
        statement = (
            update(VerificationCode)
            .where(
                VerificationCode.user_id == user_id,
                VerificationCode.purpose == purpose,
                VerificationCode.consumed_at.is_(None),
            )
            .values(consumed_at=consumed_at)
        )
        result = self.db.execute(statement)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return int(result.rowcount or 0)

    def get_latest_by_user_and_purpose(
        self,
        *,
        user_id: UUID,
        purpose: VerificationCodePurpose,
    ) -> VerificationCode | None:
        statement = (
            select(VerificationCode)
            .where(
                VerificationCode.user_id == user_id,
                VerificationCode.purpose == purpose,
            )
            .order_by(VerificationCode.created_at.desc())
        )
        return self.db.scalar(statement)

    def mark_consumed(
        self,
        *,
        verification_code: VerificationCode,
        consumed_at: datetime,
        commit: bool = True,
    ) -> VerificationCode:
        verification_code.consumed_at = consumed_at
        self.db.add(verification_code)
        if commit:
            self.db.commit()
            self.db.refresh(verification_code)
        else:
            self.db.flush()
            self.db.refresh(verification_code)
        return verification_code
