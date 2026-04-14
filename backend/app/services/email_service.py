"""
Async email service via SMTP.
"""

from __future__ import annotations

import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aiosmtplib

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Notification types that trigger email
EMAIL_ENABLED_TYPES = {
    "shift_published",
    "swap_requested",
    "swap_accepted",
    "swap_approved",
    "swap_rejected",
}


async def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
) -> bool:
    """Send an email via SMTP. Returns True on success."""
    if not settings.EMAIL_ENABLED or not settings.SMTP_HOST:
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=settings.SMTP_USE_TLS,
            timeout=10,
        )
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def _build_notification_email(title: str, message: str) -> str:
    """Build a simple HTML email body for a notification."""
    return f"""<!DOCTYPE html>
<html lang="pt">
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
  <div style="background: #1a1f2c; color: #ffffff; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="margin: 0; font-size: 24px;">Shifting</h1>
  </div>
  <div style="background: #ffffff; padding: 24px; border-radius: 0 0 8px 8px; border: 1px solid #e0e0e0;">
    <h2 style="color: #1a1f2c; margin-top: 0;">{title}</h2>
    <p style="color: #333; font-size: 15px; line-height: 1.6;">{message}</p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
    <p style="color: #999; font-size: 12px;">Esta é uma notificação automática do Shifting. Não responda a este email.</p>
  </div>
</body>
</html>"""


async def send_notification_email(
    to_email: str,
    notification_type: str,
    title: str,
    message: str,
) -> None:
    """
    Send a notification email in the background (fire-and-forget).
    Only sends for types in EMAIL_ENABLED_TYPES.
    """
    if notification_type not in EMAIL_ENABLED_TYPES:
        return

    html = _build_notification_email(title, message)
    # Fire and forget — don't block the notification flow
    asyncio.create_task(
        send_email(to_email, f"Shifting — {title}", html, body_text=message)
    )
