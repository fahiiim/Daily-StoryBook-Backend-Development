from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.repositories.verification_code_repository import VerificationCodeRepository
from app.services.verification_service import VerificationService


def get_verification_service(db: Session = Depends(get_db_session)) -> VerificationService:
    return VerificationService(VerificationCodeRepository(db))
