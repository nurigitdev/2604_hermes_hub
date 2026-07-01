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

## Hermes Gateway Hook PoC

The Gateway Hook PoC maps Hermes hook JSON into Hub message/event ingest payloads
while preserving the original hook body in `raw_payload`. Hermes observer payloads
use numeric message type codes in Hub storage: `1=pre_llm_call`,
`2=post_llm_call`, `3=pre_tool_call`, and `4=post_tool_call`. The hook keeps
the current turn text in normalized fields and excludes the cumulative
`conversation_history` list from stored raw payloads.

```bash
export HERMES_HUB_URL="http://127.0.0.1:8000"
export HERMES_AGENT_UID="agent_..."
export HERMES_API_TOKEN="hub_api_..."

python3 integrations/hermes_gateway_hook/handler.py \
  --dry-run \
  --event-file sample-hook-payload.json
```

Copy `integrations/hermes_gateway_hook/HOOK.yaml` and `handler.py` into the
Hermes Gateway hook directory when testing with the real Gateway runtime. The
handler accepts stdin JSON by default and supports `--dry-run` for payload mapping
inspection before sending anything to Hub.

## Admin Web Shell

The first Admin screen is served directly by FastAPI:

- Login: `http://127.0.0.1:8000/admin/login`
- Dashboard: `http://127.0.0.1:8000/admin/dashboard`
- Agent Registry: `http://127.0.0.1:8000/admin/agents`
- Message Explorer: `http://127.0.0.1:8000/admin/messages`

The dashboard uses the existing admin session cookie and reads
`/admin/api/dashboard/summary` for the first-screen metrics.
The Message Explorer opens message rows in a detail drawer backed by
`/admin/api/messages/{message_id}` so admins can inspect content, related
request/response messages, tool calls, and raw payload JSON.
