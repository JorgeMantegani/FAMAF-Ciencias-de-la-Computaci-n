import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from app.core.config import get_settings


class EmailSender(Protocol):
    def send_verification(self, email: str, url: str) -> None: ...

    def send_password_reset(self, email: str, url: str) -> None: ...


class SMTPEmailSender:
    def send_verification(self, email: str, url: str) -> None:
        self._send(
            email,
            "Confirmá tu cuenta de FutBot",
            f"Confirmá tu correo entrando a este enlace:\n{url}\n"
            "Si no creaste esta cuenta, ignorá este mensaje.",
        )

    def send_password_reset(self, email: str, url: str) -> None:
        self._send(
            email,
            "Recuperá tu contraseña de FutBot",
            f"Elegí una nueva contraseña entrando a este enlace:\n{url}\n"
            "El enlace tiene una duración limitada y solo puede usarse una vez.\n"
            "Si no solicitaste este cambio, ignorá este mensaje.",
        )

    def _send(self, email: str, subject: str, body: str) -> None:
        settings = get_settings()
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.smtp_from
        message["To"] = email
        message.set_content(body)
        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
        ) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)


def get_email_sender() -> EmailSender:
    if get_settings().email_sender != "smtp":
        raise ValueError("EMAIL_SENDER no soportado")
    return SMTPEmailSender()


def log_email_error(logger: logging.Logger, operation: str, error: Exception) -> None:
    """Registra diagnóstico sin textos del proveedor, destinatarios ni secretos."""
    codes = []
    if isinstance(error, smtplib.SMTPResponseException):
        codes = [error.smtp_code]
    elif isinstance(error, smtplib.SMTPRecipientsRefused):
        codes = [response[0] for response in error.recipients.values()]
    safe_codes = sorted({code for code in codes if isinstance(code, int)})
    logger.warning(
        "No se pudo enviar el correo de %s (tipo=%s, códigos SMTP=%s)",
        operation,
        type(error).__name__,
        safe_codes,
    )
