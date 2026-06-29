import anyio
import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.admin_seed import seed_admin_user
from app.services.agent_tokens import issue_enrollment_token


async def post_enroll(app: FastAPI, payload: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/agents/enroll", json=payload)


async def post_event_ingest(
    app: FastAPI,
    payload: dict[str, object],
    api_token: str | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    headers = {}
    if api_token is not None:
        headers["Authorization"] = f"Bearer {api_token}"

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/events/ingest", json=payload, headers=headers)


async def login_and_get_admin_events(
    app: FastAPI,
    path: str = "/admin/api/events",
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "change-me-admin-password"},
        )
        return await client.get(path)


async def get_admin_events_without_login(
    app: FastAPI,
    path: str = "/admin/api/events",
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


def seed_admin(db_session: Session) -> None:
    seed_admin_user(
        db_session,
        Settings(
            admin_email="admin@example.com",
            admin_name="Admin User",
            admin_password="change-me-admin-password",
        ),
    )


def enrollment_payload(enrollment_token: str | None = None) -> dict[str, str]:
    payload = {
        "profile_name": "kim-teamlead",
        "hostname": "KIM-PC",
        "ip_addr": "192.168.0.25",
        "source": "gateway",
    }
    if enrollment_token is not None:
        payload["enrollment_token"] = enrollment_token
    return payload


def event_payload(agent_uid: str) -> dict[str, object]:
    return {
        "agent_uid": agent_uid,
        "event_type": "agent:end",
        "severity": "INFO",
        "summary": "Agent response completed",
        "occurred_at": "2026-06-25T09:31:15+09:00",
        "raw_payload": {"duration_ms": 1200},
    }


def create_ingested_event(
    test_app: FastAPI,
    db_session: Session,
    *,
    event_type: str = "agent:end",
    severity: str = "INFO",
    summary: str = "Agent response completed",
) -> dict[str, object]:
    issued_token = issue_enrollment_token(db_session, owner_email="agent.owner@example.com")
    enroll_response = anyio.run(post_enroll, test_app, enrollment_payload(issued_token.token))
    enroll_body = enroll_response.json()
    payload = event_payload(enroll_body["agent_uid"])
    payload["event_type"] = event_type
    payload["severity"] = severity
    payload["summary"] = summary
    ingest_response = anyio.run(
        post_event_ingest,
        test_app,
        payload,
        enroll_body["api_token"],
    )
    return {
        "agent_uid": enroll_body["agent_uid"],
        "event_id": ingest_response.json()["event_id"],
    }


def test_admin_can_search_events(test_app: FastAPI, db_session: Session) -> None:
    seed_admin(db_session)
    created = create_ingested_event(test_app, db_session)

    response = anyio.run(login_and_get_admin_events, test_app)

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 1
    assert body["items"] == [
        {
            "id": created["event_id"],
            "occurred_at": "2026-06-25T09:31:15",
            "agent_uid": created["agent_uid"],
            "event_type": "agent:end",
            "severity": "INFO",
            "summary": "Agent response completed",
        }
    ]


def test_admin_event_search_filters_by_query_values(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)
    first = create_ingested_event(test_app, db_session, summary="alpha event")
    create_ingested_event(
        test_app,
        db_session,
        event_type="agent:error",
        severity="ERROR",
        summary="beta event",
    )

    path = (
        "/admin/api/events?"
        f"agent_uid={first['agent_uid']}&"
        "severity=INFO&event_type=agent:end&keyword=alpha&"
        "date_from=2026-06-25T00:00:00Z&date_to=2026-06-26T00:00:00Z"
    )
    response = anyio.run(login_and_get_admin_events, test_app, path)

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 1
    assert body["items"][0]["id"] == first["event_id"]
    assert body["items"][0]["summary"] == "alpha event"


def test_admin_event_search_supports_pagination(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)
    first = create_ingested_event(test_app, db_session, summary="first event")
    second = create_ingested_event(test_app, db_session, summary="second event")

    response = anyio.run(
        login_and_get_admin_events,
        test_app,
        "/admin/api/events?limit=1&offset=1",
    )

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] in {first["event_id"], second["event_id"]}


def test_admin_events_require_admin_session(test_app: FastAPI) -> None:
    response = anyio.run(get_admin_events_without_login, test_app)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
