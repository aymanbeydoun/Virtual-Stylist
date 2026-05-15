# Virtual Stylist API

FastAPI service powering the Virtual Stylist app.

## Quick start

```bash
# install deps
uv sync

# run Postgres + Redis (assumes docker)
docker compose -f ../../infra/dev/docker-compose.yaml up -d

# migrate
uv run alembic upgrade head

# serve
uv run uvicorn app.main:app --reload --port 8000

# worker
uv run arq app.services.ingest_worker.WorkerSettings
```

Set `DEV_AUTH_BYPASS=true` in `.env` to skip JWT verification locally; the
API then trusts an `X-Dev-User-Id` header and provisions the user on first
hit. Switch to a real Auth0/Clerk JWKS in any non-dev environment.

## Layout

```
app/
  main.py              FastAPI app
  config.py            Settings
  db.py                SQLAlchemy engine + session
  models/              SQLAlchemy ORM models
  schemas/             Pydantic request/response schemas
  api/v1/              Routers
  services/            Business logic (model gateway, weather, stylist)
  core/                Auth, security, storage abstractions
alembic/               Migrations
tests/                 Pytest
```
