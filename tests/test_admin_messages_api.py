import anyio
import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.agent_message import AgentMessage
from app.services.admin_seed import seed_admin_user
from app.services.agent_tokens import issue_enrollment_token


async def post_enroll(app: FastAPI, payload: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/agents/enroll", json=payload)


async def post_message_ingest(
    app: FastAPI,
    payload: dict[str, object],
    api_token: str | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    headers = {}
    if api_token is not None:
        headers["Authorization"] = f"Bearer {api_token}"

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/messages/ingest", json=payload, headers=headers)


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


def message_payload(agent_uid: str) -> dict[str, object]:
    return {
        "agent_uid": agent_uid,
        "idempotency_key": "body-idempotency-key",
        "external_message_id": "telegram_123456789_100",
        "event_type": "message",
        "source": "telegram",
        "session_key": "agent:main:telegram:private:123456789",
        "direction": "INBOUND",
        "role": "user",
        "content": "오늘 작업 내용을 정리해줘",
        "request_id": "req_abc123",
        "occurred_at": "2026-06-25T09:30:00+09:00",
        "raw_payload": {"telegram_update_id": 100},
    }


async def login_and_get_admin_messages(
    app: FastAPI,
    path: str = "/admin/api/messages",
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "change-me-admin-password"},
        )
        return await client.get(path)


async def get_admin_messages_without_login(
    app: FastAPI,
    path: str = "/admin/api/messages",
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


def create_ingested_message(
    test_app: FastAPI,
    db_session: Session,
    *,
    owner_email: str = "agent.owner@example.com",
    content: str = "오늘 작업 내용을 정리해줘",
    source: str = "telegram",
    role: str = "user",
    event_type: str = "message",
    external_message_id: str = "telegram_123456789_100",
) -> dict[str, object]:
    issued_token = issue_enrollment_token(db_session, owner_email=owner_email)
    enroll_response = anyio.run(post_enroll, test_app, enrollment_payload(issued_token.token))
    enroll_body = enroll_response.json()
    payload = message_payload(enroll_body["agent_uid"])
    payload["content"] = content
    payload["source"] = source
    payload["role"] = role
    payload["event_type"] = event_type
    payload["external_message_id"] = external_message_id
    ingest_response = anyio.run(
        post_message_ingest,
        test_app,
        payload,
        enroll_body["api_token"],
    )
    return {
        "agent_uid": enroll_body["agent_uid"],
        "message_id": ingest_response.json()["message_id"],
    }


def test_admin_can_search_messages(test_app: FastAPI, db_session: Session) -> None:
    seed_admin(db_session)
    created = create_ingested_message(test_app, db_session)

    response = anyio.run(login_and_get_admin_messages, test_app)

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 1
    assert body["items"] == [
        {
            "id": created["message_id"],
            "occurred_at": "2026-06-25T09:30:00",
            "agent_uid": created["agent_uid"],
            "profile_name": "kim-teamlead",
            "owner_email": "agent.owner@example.com",
            "source": "telegram",
            "role": "user",
            "event_type": "message",
            "content_preview": "오늘 작업 내용을 정리해줘",
        }
    ]


def test_admin_message_search_filters_by_query_values(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)
    first = create_ingested_message(test_app, db_session, content="alpha report")
    create_ingested_message(
        test_app,
        db_session,
        owner_email="other.owner@example.com",
        content="beta report",
        source="slack",
        role="assistant",
        event_type="agent:end",
        external_message_id="slack_200",
    )

    path = (
        "/admin/api/messages?"
        f"agent_uid={first['agent_uid']}&"
        "owner_email=agent.owner@example.com&"
        "source=telegram&role=user&event_type=message&keyword=alpha&"
        "date_from=2026-06-25T00:00:00Z&date_to=2026-06-26T00:00:00Z"
    )
    response = anyio.run(login_and_get_admin_messages, test_app, path)

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 1
    assert body["items"][0]["id"] == first["message_id"]
    assert body["items"][0]["content_preview"] == "alpha report"


def test_admin_message_search_supports_pagination(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)
    first = create_ingested_message(test_app, db_session, external_message_id="telegram_100")
    second = create_ingested_message(
        test_app,
        db_session,
        content="second message",
        external_message_id="telegram_101",
    )

    response = anyio.run(
        login_and_get_admin_messages,
        test_app,
        "/admin/api/messages?limit=1&offset=1",
    )

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] in {first["message_id"], second["message_id"]}


def test_admin_can_get_message_detail(test_app: FastAPI, db_session: Session) -> None:
    seed_admin(db_session)
    created = create_ingested_message(test_app, db_session)

    response = anyio.run(
        login_and_get_admin_messages,
        test_app,
        f"/admin/api/messages/{created['message_id']}",
    )

    body = response.json()
    assert response.status_code == 200
    assert body == {
        "id": created["message_id"],
        "agent_uid": created["agent_uid"],
        "session_key": "agent:main:telegram:private:123456789",
        "request_id": "req_abc123",
        "parent_message_id": None,
        "role": "user",
        "direction": "INBOUND",
        "content": "오늘 작업 내용을 정리해줘",
        "tool_calls_json": None,
        "raw_payload": {"telegram_update_id": 100},
        "related_messages": [],
    }


def test_admin_message_detail_includes_related_messages(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)
    created = create_ingested_message(test_app, db_session)
    parent_message_id = created["message_id"]
    message = db_session.get(AgentMessage, parent_message_id)
    assert message is not None
    related = AgentMessage(
        agent_id=message.agent_id,
        session_id=message.session_id,
        external_message_id="telegram_123456789_101",
        idempotency_key="related-idempotency-key",
        direction="OUTBOUND",
        role="assistant",
        event_type="agent:end",
        content="정리 결과입니다",
        content_hash="related-content-hash",
        source=message.source,
        request_id=message.request_id,
        parent_message_id=message.id,
        raw_payload="{}",
        occurred_at=message.occurred_at,
    )
    db_session.add(related)
    db_session.commit()

    response = anyio.run(
        login_and_get_admin_messages,
        test_app,
        f"/admin/api/messages/{parent_message_id}",
    )

    assert response.status_code == 200
    assert response.json()["related_messages"] == [
        {
            "id": related.id,
            "occurred_at": "2026-06-25T09:30:00",
            "request_id": "req_abc123",
            "parent_message_id": parent_message_id,
            "role": "assistant",
            "direction": "OUTBOUND",
            "event_type": "agent:end",
            "content_preview": "정리 결과입니다",
        }
    ]


def test_admin_message_detail_rejects_missing_message(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)

    response = anyio.run(login_and_get_admin_messages, test_app, "/admin/api/messages/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Message not found"}


def test_admin_messages_require_admin_session(test_app: FastAPI) -> None:
    response = anyio.run(get_admin_messages_without_login, test_app)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_admin_message_detail_handles_raw_payload_fallback(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)
    created = create_ingested_message(test_app, db_session)
    message = db_session.get(AgentMessage, created["message_id"])
    assert message is not None
    message.raw_payload = "not-json"
    db_session.commit()

    response = anyio.run(
        login_and_get_admin_messages,
        test_app,
        f"/admin/api/messages/{created['message_id']}",
    )

    assert response.status_code == 200
    assert response.json()["raw_payload"] == {"_raw": "not-json"}
