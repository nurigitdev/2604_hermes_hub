from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

JsonObject = dict[str, Any]
Transport = Callable[[str, JsonObject, Mapping[str, str]], JsonObject]

DEFAULT_PROFILE_NAME = "hermes-smoke"
DEFAULT_SOURCE = "gateway"
DEFAULT_IP_ADDR = "127.0.0.1"
DEFAULT_SESSION_KEY = "smoke:hermes:contract"


class SmokeClientError(Exception):
    pass


@dataclass(frozen=True)
class SmokeConfig:
    hub_url: str
    agent_uid: str
    api_token: str
    profile_name: str = DEFAULT_PROFILE_NAME
    hostname: str = "localhost"
    ip_addr: str = DEFAULT_IP_ADDR
    source: str = DEFAULT_SOURCE
    session_key: str = DEFAULT_SESSION_KEY
    request_id: str = "smoke-request"

    @property
    def normalized_hub_url(self) -> str:
        return self.hub_url.rstrip("/")


@dataclass(frozen=True)
class SmokeRunResult:
    heartbeat: JsonObject
    request_message: JsonObject
    response_message: JsonObject
    event: JsonObject

    def as_dict(self) -> JsonObject:
        return {
            "heartbeat": self.heartbeat,
            "request_message": self.request_message,
            "response_message": self.response_message,
            "event": self.event,
        }


def utc_timestamp(now: datetime | None = None) -> str:
    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC).isoformat()


def build_heartbeat_payload(config: SmokeConfig) -> JsonObject:
    return {
        "agent_uid": config.agent_uid,
        "profile_name": config.profile_name,
        "source": config.source,
        "ip_addr": config.ip_addr,
        "runtime_status": "smoke",
    }


def build_request_message_payload(config: SmokeConfig, *, occurred_at: str) -> JsonObject:
    return {
        "agent_uid": config.agent_uid,
        "idempotency_key": f"{config.request_id}:request",
        "external_message_id": f"{config.request_id}:request",
        "event_type": "agent:start",
        "source": config.source,
        "session_key": config.session_key,
        "direction": "INBOUND",
        "role": "user",
        "content": "Hermes Hub smoke request",
        "request_id": config.request_id,
        "parent_message_id": None,
        "occurred_at": occurred_at,
        "raw_payload": {
            "probe": "hermes_smoke_client",
            "kind": "request",
            "request_id": config.request_id,
        },
    }


def build_response_message_payload(
    config: SmokeConfig,
    *,
    occurred_at: str,
    parent_message_id: int | None,
) -> JsonObject:
    return {
        "agent_uid": config.agent_uid,
        "idempotency_key": f"{config.request_id}:response",
        "external_message_id": f"{config.request_id}:response",
        "event_type": "agent:end",
        "source": config.source,
        "session_key": config.session_key,
        "direction": "OUTBOUND",
        "role": "assistant",
        "content": "Hermes Hub smoke response",
        "request_id": config.request_id,
        "parent_message_id": parent_message_id,
        "occurred_at": occurred_at,
        "raw_payload": {
            "probe": "hermes_smoke_client",
            "kind": "response",
            "request_id": config.request_id,
            "parent_message_id": parent_message_id,
        },
    }


def build_event_payload(config: SmokeConfig, *, occurred_at: str) -> JsonObject:
    return {
        "agent_uid": config.agent_uid,
        "event_type": "agent:smoke",
        "severity": "INFO",
        "summary": "Hermes Hub smoke client completed",
        "occurred_at": occurred_at,
        "raw_payload": {
            "probe": "hermes_smoke_client",
            "request_id": config.request_id,
        },
    }


def build_dry_run_payloads(config: SmokeConfig, *, now: datetime | None = None) -> JsonObject:
    occurred_at = utc_timestamp(now)
    return {
        "heartbeat": build_heartbeat_payload(config),
        "request_message": build_request_message_payload(config, occurred_at=occurred_at),
        "response_message": build_response_message_payload(
            config,
            occurred_at=occurred_at,
            parent_message_id=None,
        ),
        "event": build_event_payload(config, occurred_at=occurred_at),
    }


def run_smoke_sequence(
    config: SmokeConfig,
    *,
    transport: Transport | None = None,
    now: datetime | None = None,
) -> SmokeRunResult:
    occurred_at = utc_timestamp(now)
    post_json = transport or UrlLibTransport(config).post_json
    headers = authorization_headers(config)

    heartbeat = post_json(
        "/api/v1/agents/heartbeat",
        build_heartbeat_payload(config),
        headers,
    )
    request_message = post_json(
        "/api/v1/messages/ingest",
        build_request_message_payload(config, occurred_at=occurred_at),
        headers,
    )
    request_message_id = require_int(request_message, "message_id")
    response_message = post_json(
        "/api/v1/messages/ingest",
        build_response_message_payload(
            config,
            occurred_at=occurred_at,
            parent_message_id=request_message_id,
        ),
        headers,
    )
    require_int(response_message, "message_id")
    event = post_json(
        "/api/v1/events/ingest",
        build_event_payload(config, occurred_at=occurred_at),
        headers,
    )
    require_int(event, "event_id")

    return SmokeRunResult(
        heartbeat=heartbeat,
        request_message=request_message,
        response_message=response_message,
        event=event,
    )


def authorization_headers(config: SmokeConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.api_token}"}


def require_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise SmokeClientError(f"Expected integer '{key}' in response: {payload}")
    return value


class UrlLibTransport:
    def __init__(self, config: SmokeConfig, *, timeout_seconds: float = 10.0) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    def post_json(self, path: str, payload: JsonObject, headers: Mapping[str, str]) -> JsonObject:
        url = f"{self.config.normalized_hub_url}{path}"
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        request = Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                **dict(headers),
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return decode_json_response(response.read())
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            message = f"POST {path} failed with HTTP {exc.code}: {error_body}"
            raise SmokeClientError(message) from exc
        except URLError as exc:
            raise SmokeClientError(f"POST {path} failed: {exc.reason}") from exc


def decode_json_response(raw_body: bytes) -> JsonObject:
    try:
        value = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SmokeClientError("Expected JSON response from Hub") from exc
    if not isinstance(value, dict):
        raise SmokeClientError(f"Expected JSON object response from Hub: {value}")
    return value


def config_from_env(env: Mapping[str, str]) -> SmokeConfig:
    request_id = env.get("HERMES_SMOKE_REQUEST_ID") or f"smoke-{uuid.uuid4().hex}"
    return SmokeConfig(
        hub_url=require_env(env, "HERMES_HUB_URL"),
        agent_uid=require_env(env, "HERMES_AGENT_UID"),
        api_token=require_env(env, "HERMES_API_TOKEN"),
        profile_name=env.get("HERMES_SMOKE_PROFILE_NAME", DEFAULT_PROFILE_NAME),
        hostname=env.get("HERMES_SMOKE_HOSTNAME", socket.gethostname()),
        ip_addr=env.get("HERMES_SMOKE_IP_ADDR", DEFAULT_IP_ADDR),
        source=env.get("HERMES_SMOKE_SOURCE", DEFAULT_SOURCE),
        session_key=env.get("HERMES_SMOKE_SESSION_KEY", DEFAULT_SESSION_KEY),
        request_id=request_id,
    )


def require_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not value:
        raise SmokeClientError(f"Missing required environment variable: {name}")
    return value


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe Hermes Agent Hub ingest API contracts.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without sending them.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = config_from_env(os.environ)
        if args.dry_run:
            output = build_dry_run_payloads(config)
        else:
            output = run_smoke_sequence(config).as_dict()
    except SmokeClientError as exc:
        print(f"Smoke probe failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
