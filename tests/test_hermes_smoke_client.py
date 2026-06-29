import sys
from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

SMOKE_CLIENT_PATH = Path(__file__).resolve().parents[1] / "tools" / "hermes_smoke_client.py"
SMOKE_CLIENT_SPEC = spec_from_file_location("hermes_smoke_client", SMOKE_CLIENT_PATH)
assert SMOKE_CLIENT_SPEC is not None
smoke_client = module_from_spec(SMOKE_CLIENT_SPEC)
sys.modules[SMOKE_CLIENT_SPEC.name] = smoke_client
assert SMOKE_CLIENT_SPEC.loader is not None
SMOKE_CLIENT_SPEC.loader.exec_module(smoke_client)

SmokeClientError = smoke_client.SmokeClientError
SmokeConfig = smoke_client.SmokeConfig
build_dry_run_payloads = smoke_client.build_dry_run_payloads
build_event_payload = smoke_client.build_event_payload
build_heartbeat_payload = smoke_client.build_heartbeat_payload
build_request_message_payload = smoke_client.build_request_message_payload
build_response_message_payload = smoke_client.build_response_message_payload
config_from_env = smoke_client.config_from_env
decode_json_response = smoke_client.decode_json_response
require_int = smoke_client.require_int
run_smoke_sequence = smoke_client.run_smoke_sequence


def smoke_config() -> SmokeConfig:
    return SmokeConfig(
        hub_url="http://127.0.0.1:8000/",
        agent_uid="agent_20260629_0001",
        api_token="hub_api_test",
        profile_name="kim-teamlead",
        hostname="KIM-PC",
        ip_addr="192.168.0.25",
        source="gateway",
        session_key="agent:main:telegram:private:123456789",
        request_id="req_smoke_001",
    )


def test_config_from_env_uses_required_and_optional_values() -> None:
    config = config_from_env(
        {
            "HERMES_HUB_URL": "http://127.0.0.1:8000/",
            "HERMES_AGENT_UID": "agent_20260629_0001",
            "HERMES_API_TOKEN": "hub_api_test",
            "HERMES_SMOKE_PROFILE_NAME": "kim-teamlead",
            "HERMES_SMOKE_HOSTNAME": "KIM-PC",
            "HERMES_SMOKE_IP_ADDR": "192.168.0.25",
            "HERMES_SMOKE_SOURCE": "gateway",
            "HERMES_SMOKE_SESSION_KEY": "session-1",
            "HERMES_SMOKE_REQUEST_ID": "req_smoke_001",
        }
    )

    assert config.normalized_hub_url == "http://127.0.0.1:8000"
    assert config.agent_uid == "agent_20260629_0001"
    assert config.api_token == "hub_api_test"
    assert config.profile_name == "kim-teamlead"
    assert config.hostname == "KIM-PC"
    assert config.ip_addr == "192.168.0.25"
    assert config.source == "gateway"
    assert config.session_key == "session-1"
    assert config.request_id == "req_smoke_001"


def test_config_from_env_requires_hub_url() -> None:
    with pytest.raises(SmokeClientError, match="HERMES_HUB_URL"):
        config_from_env(
            {
                "HERMES_AGENT_UID": "agent_20260629_0001",
                "HERMES_API_TOKEN": "hub_api_test",
            }
        )


def test_payload_builders_match_hub_contract() -> None:
    config = smoke_config()
    occurred_at = "2026-06-29T12:00:00+00:00"

    assert build_heartbeat_payload(config) == {
        "agent_uid": "agent_20260629_0001",
        "profile_name": "kim-teamlead",
        "source": "gateway",
        "ip_addr": "192.168.0.25",
        "runtime_status": "smoke",
    }
    assert build_request_message_payload(config, occurred_at=occurred_at) == {
        "agent_uid": "agent_20260629_0001",
        "idempotency_key": "req_smoke_001:request",
        "external_message_id": "req_smoke_001:request",
        "event_type": "agent:start",
        "source": "gateway",
        "session_key": "agent:main:telegram:private:123456789",
        "direction": "INBOUND",
        "role": "user",
        "content": "Hermes Hub smoke request",
        "request_id": "req_smoke_001",
        "parent_message_id": None,
        "occurred_at": occurred_at,
        "raw_payload": {
            "probe": "hermes_smoke_client",
            "kind": "request",
            "request_id": "req_smoke_001",
        },
    }
    assert build_response_message_payload(
        config,
        occurred_at=occurred_at,
        parent_message_id=101,
    )["parent_message_id"] == 101
    assert build_event_payload(config, occurred_at=occurred_at) == {
        "agent_uid": "agent_20260629_0001",
        "event_type": "agent:smoke",
        "severity": "INFO",
        "summary": "Hermes Hub smoke client completed",
        "occurred_at": occurred_at,
        "raw_payload": {
            "probe": "hermes_smoke_client",
            "request_id": "req_smoke_001",
        },
    }


def test_build_dry_run_payloads_uses_shared_timestamp() -> None:
    config = smoke_config()
    payloads = build_dry_run_payloads(config, now=datetime(2026, 6, 29, 12, 0, tzinfo=UTC))

    assert payloads["request_message"]["occurred_at"] == "2026-06-29T12:00:00+00:00"
    assert payloads["response_message"]["occurred_at"] == "2026-06-29T12:00:00+00:00"
    assert payloads["event"]["occurred_at"] == "2026-06-29T12:00:00+00:00"


def test_run_smoke_sequence_sends_parent_linked_pair() -> None:
    config = smoke_config()
    calls = []

    def transport(path, payload, headers):
        calls.append((path, payload, dict(headers)))
        if path == "/api/v1/agents/heartbeat":
            return {"ok": True, "agent_uid": config.agent_uid}
        if path == "/api/v1/messages/ingest" and payload["role"] == "user":
            return {"ok": True, "message_id": 101, "duplicate": False}
        if path == "/api/v1/messages/ingest" and payload["role"] == "assistant":
            return {"ok": True, "message_id": 102, "duplicate": False}
        if path == "/api/v1/events/ingest":
            return {"ok": True, "event_id": 201}
        raise AssertionError(f"Unexpected call: {path}")

    result = run_smoke_sequence(
        config,
        transport=transport,
        now=datetime(2026, 6, 29, 12, 0, tzinfo=UTC),
    )

    assert result.request_message["message_id"] == 101
    assert result.response_message["message_id"] == 102
    assert result.event["event_id"] == 201
    assert [call[0] for call in calls] == [
        "/api/v1/agents/heartbeat",
        "/api/v1/messages/ingest",
        "/api/v1/messages/ingest",
        "/api/v1/events/ingest",
    ]
    assert calls[0][2] == {"Authorization": "Bearer hub_api_test"}
    assert calls[2][1]["parent_message_id"] == 101
    assert calls[2][1]["request_id"] == "req_smoke_001"


def test_run_smoke_sequence_rejects_missing_message_id() -> None:
    config = smoke_config()

    def transport(path, _payload, _headers):
        if path == "/api/v1/agents/heartbeat":
            return {"ok": True}
        return {"ok": True}

    with pytest.raises(SmokeClientError, match="message_id"):
        run_smoke_sequence(config, transport=transport)


def test_require_int_rejects_non_integer() -> None:
    with pytest.raises(SmokeClientError, match="message_id"):
        require_int({"message_id": "101"}, "message_id")


def test_decode_json_response_requires_object() -> None:
    with pytest.raises(SmokeClientError, match="JSON object"):
        decode_json_response(b"[1, 2]")
