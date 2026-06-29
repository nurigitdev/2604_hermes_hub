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

## Hermes Integration Smoke Probe

Before wiring a real Hermes Gateway hook, run the smoke client to verify the Hub
ingest contract with an already enrolled ACTIVE Agent token.

```bash
export HERMES_HUB_URL="http://127.0.0.1:8000"
export HERMES_AGENT_UID="agent_..."
export HERMES_API_TOKEN="hub_api_..."

./.venv/bin/python tools/hermes_smoke_client.py --dry-run
./.venv/bin/python tools/hermes_smoke_client.py
```

Optional probe environment variables:

- `HERMES_SMOKE_PROFILE_NAME`
- `HERMES_SMOKE_HOSTNAME`
- `HERMES_SMOKE_IP_ADDR`
- `HERMES_SMOKE_SOURCE`
- `HERMES_SMOKE_SESSION_KEY`
- `HERMES_SMOKE_REQUEST_ID`

The smoke client sends heartbeat, request message, response message, and lifecycle
event payloads. The response message uses the request message id as
`parent_message_id`, which exercises the Message Detail pair contract.
