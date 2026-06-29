# Hermes Agent Hub

Hermes Agent Hub is the WPS v2.0 e2e minimal collector for observing Hermes Agent
request, response, message, session, and event data.

## Development Environment

The local Python virtual environment is expected at `.venv/`.

```bash
./.venv/bin/python --version
./.venv/bin/pip install -e ".[dev]"
```

The project targets Python 3.11+ and is currently prepared with Python 3.12.13.

Copy `.env.example` to `.env` for local development values. Do not commit `.env`.

SQLite file URLs are used for local development and tests:

- `HERMES_HUB_DATABASE_URL` for the local development database
- `HERMES_HUB_TEST_DATABASE_URL` for isolated test database defaults
- `HERMES_HUB_ADMIN_EMAIL` and `HERMES_HUB_ADMIN_PASSWORD` for the initial admin seed

## Quality Commands

```bash
./.venv/bin/pytest
./.venv/bin/pytest --cov=app --cov-branch --cov-report=term-missing
./.venv/bin/ruff check .
```

Coverage targets are progressive goals for v2.0. They are measured and reported first,
not used as hard commit blockers during the initial slices.

## Run Locally

```bash
./.venv/bin/uvicorn app.main:app --reload
```

The initial health endpoint is available at `/healthz`.
