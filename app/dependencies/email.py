from app.services.email_service import EmailService


def get_email_service() -> EmailService:
    return EmailService()
