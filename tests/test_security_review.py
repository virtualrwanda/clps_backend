"""Database-free security checks; run with --noconftest to avoid DB fixtures."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.core.config import Settings
from app.core.security import hash_password, hash_token, verify_password
from app.schemas.auth import VerifyLoginOTPRequest
from app.services.auth_service import _gen_otp
from app.services.session_service import SessionService, _cache


def test_default_generated_otp_is_accepted_by_api():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://unused/unused",
        database_url_sync="postgresql+psycopg://unused/unused",
    )
    VerifyLoginOTPRequest(
        challenge_id=uuid4(), code=_gen_otp(settings.login_otp_length)
    )


def test_cached_session_checks_durable_revocation():
    # Another worker can revoke the durable row without clearing this cache.
    token = "security-review-session"
    key = SessionService._key(hash_token(token))
    _cache.set(key, {"user_id": str(uuid4())}, 60)
    factory = MagicMock()
    db = factory.return_value.__aenter__.return_value
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)
    try:
        with patch("app.db.session.AsyncSessionLocal", factory):
            asyncio.run(SessionService().validate_and_touch(token))
        assert factory.called, "Cached token bypassed durable revocation lookup"
        assert _cache.get(key) is None
    finally:
        _cache.delete(key)


def test_password_hash_rejects_wrong_password_and_invalid_hash():
    hashed = hash_password("security-review-password")
    assert hashed != "security-review-password"
    assert verify_password("security-review-password", hashed)
    assert not verify_password("wrong-password", hashed)
    assert not verify_password("security-review-password", "invalid-hash")


def test_incorrect_otp_attempt_is_committed_before_error():
    from types import SimpleNamespace
    from datetime import timedelta
    import pytest
    from fastapi import HTTPException
    from app.core.timeutils import utcnow
    from app.services.auth_service import AuthService, _hash_otp

    challenge = SimpleNamespace(
        consumed_at=None, expires_at=utcnow() + timedelta(minutes=5),
        attempt_count=0, code_hash=_hash_otp("12345678"),
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = challenge
    db = AsyncMock()
    db.execute.return_value = result
    with pytest.raises(HTTPException) as error:
        asyncio.run(AuthService.verify_login_otp(db, challenge_id=uuid4(), code="00000000"))
    assert error.value.status_code == 400
    assert challenge.attempt_count == 1
    db.commit.assert_awaited_once()
