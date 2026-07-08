from app.core.logging import get_logger

logger = get_logger(__name__)


class EmailService:
    def send_email(self, *, to: str, subject: str, body: str) -> None:
        # TODO: wire up a real provider (SES/SendGrid/SMTP) before any non-local deployment.
        logger.info("email_stub_send", to=to, subject=subject, body=body)
