import sys
from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

HANDLER_PATH = (
    Path(__file__).resolve().parents[1] / "integrations" / "hermes_gateway_hook" / "handler.py"
)
HANDLER_SPEC = spec_from_file_location("hermes_gateway_hook_handler", HANDLER_PATH)
assert HANDLER_SPEC is not None
handler = module_from_spec(HANDLER_SPEC)
sys.modules[HANDLER_SPEC.name] = handler
assert HANDLER_SPEC.loader is not None
HANDLER_SPEC.loader.exec_module(handler)

HookConfig = handler.HookConfig
HookHandlerError = handler.HookHandlerError
build_hook_actions = handler.build_hook_actions
config_from_env = handler.config_from_env
decode_json_response = handler.decode_json_response
extract_parent_message_id = handler.extract_parent_message_id
read_hook_payload = handler.read_hook_payload
run_hook_event = handler.run_hook_event


def hook_config() -> HookConfig:
    return HookConfig(
        hub_url="http://127.0.0.1:8000/",
        agent_uid="agent_20260629_0001",
        api_token="hub_api_test",
        profile_name="kim-teamlead",
        hostname="KIM-PC",
        ip_addr="192.168.0.25",
        source="gateway",
        session_key="gateway:telegram:123456789",
    )


def test_config_from_env_uses_required_and_optional_values() -> None:
    config = config_from_env(
        {
            "HERMES_HUB_URL": "http://127.0.0.1:8000/",
            "HERMES_AGENT_UID": "agent_20260629_0001",
            "HERMES_API_TOKEN": "hub_api_test",
            "HERMES_HOOK_PROFILE_NAME": "kim-teamlead",
            "HERMES_HOOK_HOSTNAME": "KIM-PC",
            "HERMES_HOOK_IP_ADDR": "192.168.0.25",
            "HERMES_HOOK_SOURCE": "gateway",
            "HERMES_HOOK_SESSION_KEY": "gateway:telegram:123456789",
        }
    )

    assert config.normalized_hub_url == "http://127.0.0.1:8000"
    assert config.agent_uid == "agent_20260629_0001"
    assert config.api_token == "hub_api_test"
    assert config.profile_name == "kim-teamlead"
    assert config.hostname == "KIM-PC"
    assert config.ip_addr == "192.168.0.25"
    assert config.source == "gateway"
    assert config.session_key == "gateway:telegram:123456789"


def test_config_from_env_requires_hub_url() -> None:
    with pytest.raises(HookHandlerError, match="HERMES_HUB_URL"):
        config_from_env(
            {
                "HERMES_AGENT_UID": "agent_20260629_0001",
                "HERMES_API_TOKEN": "hub_api_test",
            }
        )


def test_build_hook_actions_maps_agent_start_to_message_and_event() -> None:
    payload = {
        "event_type": "agent:start",
        "request_id": "req-1",
        "session": {"id": "session-1"},
        "platform": "telegram",
        "prompt": "오늘 작업 내용을 정리해줘",
        "timestamp": "2026-06-29T12:00:00+00:00",
    }

    actions = build_hook_actions(hook_config(), payload)

    assert [action.endpoint for action in actions] == [
        "/api/v1/messages/ingest",
        "/api/v1/events/ingest",
    ]
    message = actions[0].payload
    assert message["agent_uid"] == "agent_20260629_0001"
    assert message["event_type"] == "agent:start"
    assert message["source"] == "telegram"
    assert message["session_key"] == "session-1"
    assert message["direction"] == "INBOUND"
    assert message["role"] == "user"
    assert message["content"] == "오늘 작업 내용을 정리해줘"
    assert message["request_id"] == "req-1"
    assert message["parent_message_id"] is None
    assert message["raw_payload"]["hook_payload"] == payload
    event = actions[1].payload
    assert event["event_type"] == "agent:start"
    assert event["summary"] == "Hermes Gateway hook received: agent:start"


def test_build_hook_actions_maps_agent_end_response_with_parent_message_id() -> None:
    payload = {
        "event": "agent:end",
        "run_id": "req-1",
        "response": "정리 결과입니다",
        "parent_message_id": "101",
        "payload": {
            "session_id": "session-1",
            "source": "slack",
        },
    }

    actions = build_hook_actions(
        hook_config(),
        payload,
        now=datetime(2026, 6, 29, 12, 0, tzinfo=UTC),
    )

    message = actions[0].payload
    assert message["role"] == "assistant"
    assert message["direction"] == "OUTBOUND"
    assert message["content"] == "정리 결과입니다"
    assert message["request_id"] == "req-1"
    assert message["parent_message_id"] == 101
    assert message["source"] == "slack"
    assert message["session_key"] == "session-1"
    assert message["occurred_at"] == "2026-06-29T12:00:00+00:00"


def test_build_hook_actions_maps_step_to_event_only() -> None:
    payload = {
        "type": "agent:step",
        "severity": "WARNING",
        "summary": "tool call started",
        "payload": {"tool": "search"},
    }

    actions = build_hook_actions(
        hook_config(),
        payload,
        now=datetime(2026, 6, 29, 12, 0, tzinfo=UTC),
    )

    assert len(actions) == 1
    assert actions[0].endpoint == "/api/v1/events/ingest"
    assert actions[0].payload["event_type"] == "agent:step"
    assert actions[0].payload["severity"] == "WARNING"
    assert actions[0].payload["summary"] == "tool call started"


def test_extract_parent_message_id_ignores_external_parent_ids() -> None:
    assert extract_parent_message_id({"parent_message_id": "101"}) == 101
    assert extract_parent_message_id({"parent_message_id": "external-101"}) is None


def test_run_hook_event_posts_actions_with_authorization_header() -> None:
    calls = []

    def transport(path, payload, headers):
        calls.append((path, payload, dict(headers)))
        if path == "/api/v1/messages/ingest":
            return {"ok": True, "message_id": 101, "duplicate": False}
        return {"ok": True, "event_id": 201}

    results = run_hook_event(
        hook_config(),
        {"event_type": "agent:start", "request_id": "req-1", "prompt": "hello"},
        transport=transport,
    )

    assert [call[0] for call in calls] == ["/api/v1/messages/ingest", "/api/v1/events/ingest"]
    assert calls[0][2] == {"Authorization": "Bearer hub_api_test"}
    assert results == [
        {
            "endpoint": "/api/v1/messages/ingest",
            "response": {"ok": True, "message_id": 101, "duplicate": False},
        },
        {"endpoint": "/api/v1/events/ingest", "response": {"ok": True, "event_id": 201}},
    ]


def test_read_hook_payload_accepts_json_object_from_stdin() -> None:
    assert read_hook_payload(None, '{"event_type": "agent:start"}') == {
        "event_type": "agent:start"
    }


def test_read_hook_payload_rejects_non_object_json() -> None:
    with pytest.raises(HookHandlerError, match="JSON object"):
        read_hook_payload(None, "[1, 2]")


def test_decode_json_response_requires_object() -> None:
    with pytest.raises(HookHandlerError, match="JSON object"):
        decode_json_response(b"[1, 2]")
