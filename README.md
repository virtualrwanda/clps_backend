# CLH Backend

FastAPI backend for Customized Learning Hub â€” subscription-based e-learning platform.
Implements Phases 1â€“2 of the CLH Technical Blueprint: project scaffold, DB schema,
authentication with single-active-session enforcement, and RBAC.

## Stack

- FastAPI + Pydantic v2
- SQLAlchemy 2.0 (async) + Alembic
- PostgreSQL 16
- Redis 7 (sessions + cache)
- Argon2id password hashing

## Quickstart

```bash
# 1. Install dependencies
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -e ".[dev]"

# 2. Start infrastructure
docker compose up -d

# 3. Create the test database (clh is created automatically)
docker exec -it clh_postgres psql -U clh -c "CREATE DATABASE clh_test;"

# 4. Configure
copy .env.example .env      # Windows
# cp .env.example .env      # macOS/Linux

# 5. Migrate
alembic upgrade head

# 6. Seed RBAC + settings
python -m scripts.seed_rbac

# 7. Run
uvicorn app.main:app --reload --port 8000
```

- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

## Tests

```bash
# ensure clh_test DB exists (see step 3 above)
pytest -v
```

## What's implemented (Phase 1â€“2)

- âœ… Project scaffold and env-driven config (no hard-coded secrets)
- âœ… Full Postgres schema via SQLAlchemy 2.0 + Alembic migrations
- âœ… Argon2id password hashing, opaque session tokens
- âœ… **Single-active-session enforcement** â€” new login revokes prior session (Redis + DB)
- âœ… Table-driven RBAC (roles, permissions, role_permissions, user_roles)
- âœ… `require_permissions()` / `require_roles()` route guards
- âœ… `SystemSetting` table â€” every business value configurable (Rule 3)
- âœ… Audit log model + `AuditService` (immutable by convention; DB trigger to come)
- âœ… Security headers middleware, HttpOnly + SameSite cookie

## What's next (Phase 3+)

- Content CMS routes (curricula â†’ grades â†’ subjects â†’ courses â†’ units â†’ lessons)
- Video pipeline (managed service, playback-token endpoint)
- Payment abstraction (MoMo, PayPal) with idempotent webhook handlers
- Subscription state machine + nightly expiry sweep
- Notification queue (ARQ / Celery)
- Reports + CSV/PDF export