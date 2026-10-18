"""
Email service.

- EMAIL_MOCK=true  -> logs the message to the console (no SMTP needed)
- EMAIL_MOCK=false -> sends via SMTP using aiosmtplib

Config comes from Settings (see app/core/config.py).
"""
from __future__ import annotations

import logging
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger("clh.email")
_settings = get_settings()


async def _send(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> None:
    if _settings.email_mock or not _settings.mail_server:
        logger.info(
            "[MOCK EMAIL] to=%s subject=%s\n%s",
            to_email, subject, text_body,
        )
        return

    msg = EmailMessage()
    msg["From"] = f"{_settings.mail_from_name} <{_settings.mail_from}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        import aiosmtplib

        username = _settings.mail_username if _settings.mail_use_credentials else None
        password = _settings.mail_password if _settings.mail_use_credentials else None

        if _settings.mail_ssl_tls:
            # Implicit TLS (SMTPS) — port 465
            await aiosmtplib.send(
                msg,
                hostname=_settings.mail_server,
                port=_settings.mail_port,
                username=username,
                password=password,
                use_tls=True,
                timeout=20,
            )
        else:
            # STARTTLS — port 587
            await aiosmtplib.send(
                msg,
                hostname=_settings.mail_server,
                port=_settings.mail_port,
                username=username,
                password=password,
                start_tls=_settings.mail_starttls,
                timeout=20,
            )

        logger.info("Sent email to %s: %s", to_email, subject)

    except Exception:
        logger.exception("Failed to send email to %s (subject=%s)", to_email, subject)


# ==================================================================
# Specific emails
# ==================================================================
async def send_verification_email(to_email: str, token: str) -> None:
    url = f"http://localhost:3000/verify-email?token={token}"
    await _send(
        to_email=to_email,
        subject="Verify your Customized Learning Hub account",
        text_body=f"Welcome to CLH!\n\nConfirm your email: {url}\n\nThis link expires in 24 hours.",
    )


async def send_password_reset_email(to_email: str, token: str) -> None:
    url = f"http://localhost:3000/reset-password?token={token}"
    await _send(
        to_email=to_email,
        subject="Reset your CLH password",
        text_body=f"Reset your password: {url}\n\nThis link expires in 1 hour.",
    )


async def send_login_otp_email(to_email: str, code: str, expires_minutes: int) -> None:
    await _send(
        to_email=to_email,
        subject=f"Your CLH login code: {code}",
        text_body=(
            f"Your one-time login code is:\n\n"
            f"    {code}\n\n"
            f"It expires in {expires_minutes} minute(s).\n"
            f"If you didn't try to log in, ignore this email and change your password."
        ),
    )


async def send_subscription_activated(to_email: str) -> None:
    await _send(
        to_email=to_email,
        subject="Your CLH subscription is active",
        text_body="Thanks for subscribing! Your account now has full access.",
    )


async def send_renewal_reminder(to_email: str, days_before: int) -> None:
    await _send(
        to_email=to_email,
        subject=f"Your CLH subscription expires in {days_before} day(s)",
        text_body=f"Renew now to keep access: http://localhost:3000/subscription",
    )


async def send_tutor_approved(to_email: str) -> None:
    await _send(
        to_email=to_email,
        subject="Your CLH tutor profile was approved",
        text_body="Congratulations! Your tutor profile is now visible to students.",
    )


async def send_tutor_rejected(to_email: str, reason: str) -> None:
    await _send(
        to_email=to_email,
        subject="Your CLH tutor profile needs changes",
        text_body=f"Your profile was not approved.\n\nReason: {reason}\n\nUpdate and resubmit.",
    )