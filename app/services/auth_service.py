"""
Auth service â€” register, password authenticate, OTP login, change password.

Timezone rule: never compare datetimes directly. Use app.core.timeutils.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.core.timeutils import as_utc, is_past, utcnow
from app.models.login_otp import LoginOTP
from app.models.rbac import Role, UserRole
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.auth import SELF_REGISTRABLE_ROLES
from app.services import email_service

_settings = get_settings()


def _hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _gen_otp(length: int) -> str:
    upper = 10 ** length
    n = secrets.randbelow(upper)
    return str(n).zfill(length)


class AuthService:
    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    @staticmethod
    async def register(
        db: AsyncSession,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        school_name: str | None = None,
        grade_id: UUID | None = None,
        country: str | None = None,
        role: str = "student",
    ) -> User:
        email = email.lower().strip()

        if role not in SELF_REGISTRABLE_ROLES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Role '{role}' cannot be self-registered. "
                f"Allowed: {', '.join(SELF_REGISTRABLE_ROLES)}",
            )

        existing = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

        user = User(
            email=email,
            password_hash=hash_password(password),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            school_name=school_name,
            current_grade_id=grade_id,
            country=country,
            status="active",
        )
        db.add(user)
        await db.flush()

        requested_role = (
            await db.execute(select(Role).where(Role.name == role))
        ).scalar_one_or_none()
        if requested_role is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Role '{role}' missing from database â€” run seed_rbac",
            )
        db.add(UserRole(user_id=user.id, role_id=requested_role.id))

        if role == "tutor":
            db.add(TutorProfile(user_id=user.id, status="draft"))

        return user

    # ------------------------------------------------------------------
    # Password check
    # ------------------------------------------------------------------
    @staticmethod
    async def authenticate(db: AsyncSession, *, email: str, password: str) -> User:
        email = email.lower().strip()
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")
        return user

    # ------------------------------------------------------------------
    # OTP: start
    # ------------------------------------------------------------------
    @staticmethod
    async def start_login_verification(
        db: AsyncSession, user: User
    ) -> tuple[LoginOTP, str]:
        now = utcnow()

        # Consume prior unconsumed challenges
        prior = (
            await db.execute(
                select(LoginOTP).where(
                    LoginOTP.user_id == user.id,
                    LoginOTP.consumed_at.is_(None),
                )
            )
        ).scalars().all()
        for p in prior:
            p.consumed_at = now

        code = _gen_otp(_settings.login_otp_length)
        challenge = LoginOTP(
            user_id=user.id,
            code_hash=_hash_otp(code),
            expires_at=now + timedelta(seconds=_settings.login_otp_ttl_seconds),
            attempt_count=0,
        )
        db.add(challenge)
        await db.flush()

        await email_service.send_login_otp_email(
            user.email,
            code,
            max(1, _settings.login_otp_ttl_seconds // 60),
        )
        return challenge, code

    # ------------------------------------------------------------------
    # OTP: verify
    # ------------------------------------------------------------------
    @staticmethod
    async def verify_login_otp(
        db: AsyncSession,
        *,
        challenge_id: UUID,
        code: str,
    ) -> User:
        now = utcnow()

        challenge = (
            await db.execute(
                select(LoginOTP)
                .where(LoginOTP.id == challenge_id)
                .with_for_update()
            )
        ).scalar_one_or_none()

        if challenge is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown challenge")
        if challenge.consumed_at is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code already used")

        # FIX: use tz-aware comparison
        if is_past(challenge.expires_at):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code expired")

        if challenge.attempt_count >= _settings.login_otp_max_attempts:
            challenge.consumed_at = now
            await db.commit()
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many incorrect attempts. Request a new code.",
            )

        expected_hash = _hash_otp(code.strip())
        if not hmac.compare_digest(expected_hash, challenge.code_hash):
            challenge.attempt_count += 1
            if challenge.attempt_count >= _settings.login_otp_max_attempts:
                challenge.consumed_at = now
            # Persist failed attempts before the request dependency rolls back.
            await db.commit()
            remaining = _settings.login_otp_max_attempts - challenge.attempt_count
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Incorrect code. {max(remaining, 0)} attempt(s) remaining.",
            )

        # Success
        challenge.consumed_at = now
        await db.flush()

        user = (
            await db.execute(select(User).where(User.id == challenge.user_id))
        ).scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account unavailable")
        return user

    # ------------------------------------------------------------------
    # Password change
    # ------------------------------------------------------------------
    @staticmethod
    async def change_password(
        db: AsyncSession, user: User, current: str, new: str
    ) -> None:
        if not verify_password(current, user.password_hash):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Current password is incorrect"
            )
        user.password_hash = hash_password(new)
        await db.flush()