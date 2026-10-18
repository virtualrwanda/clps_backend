import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_login_single_session(client: AsyncClient, captured_login_codes):
    # 1. Register
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "student1@example.com",
            "password": "supersecret123",
            "first_name": "Aline",
            "last_name": "K",
            "school_name": "Kigali High",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "student1@example.com"

    # 2. Password verification sends an OTP but does not create a session.
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "student1@example.com", "password": "supersecret123"},
    )
    assert r.status_code == 200, r.text
    challenge_id = r.json()["challenge_id"]
    assert not r.cookies.get("clh_session")

    r = await client.post(
        "/api/v1/auth/verify-login-otp",
        json={"challenge_id": challenge_id, "code": captured_login_codes["student1@example.com"]},
    )
    assert r.status_code == 200, r.text
    cookie1 = r.cookies.get("clh_session")
    assert cookie1

    # 3. /me works with first session
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 200

    # 4. A second verified login should invalidate session #1.
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "student1@example.com", "password": "supersecret123"},
    )
    assert r.status_code == 200
    challenge_id = r.json()["challenge_id"]
    r = await client.post(
        "/api/v1/auth/verify-login-otp",
        json={"challenge_id": challenge_id, "code": captured_login_codes["student1@example.com"]},
    )
    assert r.status_code == 200, r.text
    cookie2 = r.cookies.get("clh_session")
    assert cookie2 and cookie2 != cookie1

    # 5. Old cookie must now be rejected
    client.cookies.set("clh_session", cookie1)
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401

    # 6. New cookie works
    client.cookies.set("clh_session", cookie2)
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, captured_login_codes):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpass@example.com",
            "password": "supersecret123",
            "first_name": "Bob",
            "last_name": "M",
        },
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@example.com", "password": "nope-nope"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client: AsyncClient, captured_login_codes):
    payload = {
        "email": "dup@example.com",
        "password": "supersecret123",
        "first_name": "A",
        "last_name": "B",
    }
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_student_cannot_list_users(client: AsyncClient, captured_login_codes):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "student-perm@example.com",
            "password": "supersecret123",
            "first_name": "A",
            "last_name": "B",
        },
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "student-perm@example.com", "password": "supersecret123"},
    )
    await client.post(
        "/api/v1/auth/verify-login-otp",
        json={
            "challenge_id": r.json()["challenge_id"],
            "code": captured_login_codes["student-perm@example.com"],
        },
    )
    r = await client.get("/api/v1/users")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_login_otp_is_single_use_and_required(client: AsyncClient, captured_login_codes):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "otp@example.com",
            "password": "supersecret123",
            "first_name": "OTP",
            "last_name": "User",
        },
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "otp@example.com", "password": "supersecret123"},
    )
    challenge_id = r.json()["challenge_id"]
    assert not r.cookies.get("clh_session")

    r = await client.post(
        "/api/v1/auth/verify-login-otp",
        json={"challenge_id": challenge_id, "code": "00000000"},
    )
    assert r.status_code == 400

    code = captured_login_codes["otp@example.com"]
    r = await client.post(
        "/api/v1/auth/verify-login-otp",
        json={"challenge_id": challenge_id, "code": code},
    )
    assert r.status_code == 200
    assert r.cookies.get("clh_session")

    r = await client.post(
        "/api/v1/auth/verify-login-otp",
        json={"challenge_id": challenge_id, "code": code},
    )
    assert r.status_code == 400