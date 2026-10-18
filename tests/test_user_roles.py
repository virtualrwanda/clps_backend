"""Role responses without connecting to a database; run with --noconftest."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.auth import router
from app.core.deps import get_current_user, get_session_service
from app.db.session import get_db
from app.services.user_service import public_users


class UserWithUnloadedRoles(SimpleNamespace):
    @property
    def roles(self):
        raise AssertionError("Serializing a user must not load the ORM roles relationship")


def make_user(email="info@vrt.rw"):
    return UserWithUnloadedRoles(
        id=uuid4(), email=email, first_name="Test", last_name="Account",
        school_name=None, current_grade_id=None, country=None, status="active",
        email_verified_at=None, created_at=None,
    )


def make_db(rows):
    result = MagicMock()
    result.all.return_value = rows
    return SimpleNamespace(execute=AsyncMock(return_value=result))


@pytest.mark.parametrize("role", ["admin", "super_admin", "tutor", "content_manager", "student"])
def test_auth_responses_include_database_role(role):
    user = make_user()
    db = make_db([(user.id, role)])
    sessions = SimpleNamespace(create_session=AsyncMock(return_value="test-session"))
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session_service] = lambda: sessions

    async def check():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
            me = await client.get("/api/v1/auth/me")
            with patch("app.api.v1.auth.AuthService.verify_login_otp", AsyncMock(return_value=user)):
                login = await client.post("/api/v1/auth/verify-login-otp", json={
                    "challenge_id": str(uuid4()), "code": "12345678",
                })
            for response in (me, login):
                assert response.status_code == 200, response.text
                assert response.json()["role"] == role
                assert response.json()["roles"] == [role]
                assert "password_hash" not in response.json()

    asyncio.run(check())


def test_multiple_roles_prefer_admin_and_users_without_roles_do_not_become_students():
    admin, unassigned = make_user(), make_user("other@example.com")
    db = make_db([(admin.id, "student"), (admin.id, "admin")])
    results = asyncio.run(public_users(db, [admin, unassigned]))
    assert results[0].role == "admin"
    assert results[0].roles == ["admin", "student"]
    assert results[1].role is None
    assert results[1].roles == []
    db.execute.assert_awaited_once()
