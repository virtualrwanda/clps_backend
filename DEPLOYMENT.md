# Backend deployment

## Render

`render.yaml` defines a Docker web service with one instance, `/health` checks,
and a 1 GB disk at `/app/uploads`. It selects paid compute for persistent storage;
review the cost in Render before applying it. Automatic deploys are disabled.

Connect the Git repository containing this backend to a Render Blueprint and select
this `render.yaml`. If the backend is in a repository subdirectory, adjust
`dockerfilePath` and `dockerContext` to include that subdirectory. Provide all
`sync: false` environment values in the dashboard. Supply reachable PostgreSQL URLs,
not localhost URLs. This Blueprint does not provision a database.

Configure live payment-provider credentials separately before accepting payments.
If the frontend and API are on different sites, use
`SESSION_COOKIE_SAMESITE=none` with HTTPS and add appropriate CSRF protection.

Resolve the release blockers below before applying the Blueprint. The current
health endpoint alone does not establish that authentication or the database works.

References: https://render.com/docs/blueprint-spec and
https://render.com/docs/postgresql.

The Dockerfile packages this FastAPI backend with its PostgreSQL drivers and SMTP
dependency. Supply configuration through your host's secret/environment settings.
The image excludes local environment files and uploaded documents.

## Required configuration

- `DATABASE_URL`: async PostgreSQL URL (`postgresql+asyncpg://USER:PASSWORD@HOST:5432/clh`).
- `DATABASE_URL_SYNC`: matching `postgresql+psycopg://` URL for Alembic.
- `ENV=production` and `SESSION_COOKIE_SECURE=true` behind HTTPS.
- `CORS_ORIGINS`: exact HTTPS frontend origin, or comma-separated origins.
- `LOGIN_OTP_LENGTH=8` to match the current request schema.
- `LOGIN_OTP_RETURN_CODE_IN_RESPONSE=false`.
- `EMAIL_MOCK=false`, `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`,
  `MAIL_PASSWORD`, `MAIL_FROM`, and appropriate SMTP TLS settings.
- `MOMO_MOCK=false`, `PAYPAL_MOCK=false`, plus credentials for enabled payment providers.
- Optional `PORT` (defaults to 8000).

Use URL-encoded credentials in database URLs. Persist `/app/uploads` on a writable
volume owned by UID 10001. Terminate HTTPS at the hosting provider or reverse proxy.

## Build and start

```sh
docker build -t clh-backend .
docker run -d --name clh-backend --env-file /secure/path/clh.env \
  -p 127.0.0.1:8000:8000 -v clh_uploads:/app/uploads clh-backend
```

`GET /health` verifies the web process only; it does not check database connectivity.
Complete an OTP login and an authenticated request to verify database and SMTP access.

## Database and release blockers

Run `alembic upgrade head` to initialize PostgreSQL, then seed permissions with
`python -m scripts.seed_rbac`. Back up existing data before applying migrations.
Changing URLs does not transfer existing data; use a separate data migration.

The security review also identified OTP attempt increments being rolled back on
failed requests and session revocation bypassed by worker-local caching. Resolve
these before a public production release. One worker reduces cross-worker cache
inconsistency but does not replace a durable revocation fix.

The existing integration tests drop and recreate database tables: run them only
against a dedicated disposable test database.
