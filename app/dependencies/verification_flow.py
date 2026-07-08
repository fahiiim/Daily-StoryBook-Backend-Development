from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db_session
from app.dependencies.email import get_email_service
from app.dependencies.verification import get_verification_service
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService
from app.services.verification_flow_service import VerificationFlowService
from app.services.verification_service import VerificationService


def get_verification_flow_service(
    db: Session = Depends(get_db_session),
    verification_service: VerificationService = Depends(get_verification_service),
    email_service: EmailService = Depends(get_email_service),
) -> VerificationFlowService:
    return VerificationFlowService(
        user_repository=UserRepository(db),
        verification_service=verification_service,
        email_service=email_service,
    )
