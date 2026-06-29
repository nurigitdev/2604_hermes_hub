from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

JsonObject = dict[str, Any]
Transport = Callable[[str, JsonObject, Mapping[str, str]], JsonObject]

DEFAULT_SOURCE = "gateway"
DEFAULT_SESSION_KEY = "gateway:unknown"
DEFAULT_IP_ADDR = "127.0.0.1"
MESSAGE_EVENT_TYPES = {"agent:start", "agent:end"}
UTC = timezone.utc  # noqa: UP017 - keep handler compatible with Python 3.10 runtimes.


class HookHandlerError(Exception):
    pass


@dataclass(frozen=True)
class HookConfig:
    hub_url: str
    agent_uid: str
    api_token: str
    profile_name: str
    hostname: str
    ip_addr: str = DEFAULT_IP_ADDR
    source: str = DEFAULT_SOURCE
    session_key: str = DEFAULT_SESSION_KEY

    @property
    def normalized_hub_url(self) -> str:
        return self.hub_url.rstrip("/")


@dataclass(frozen=True)
class HookAction:
    endpoint: str
    payload: JsonObject

    def as_dict(self) -> JsonObject:
        return {"endpoint": self.endpoint, "payload": self.payload}


def utc_timestamp(now: datetime | None = None) -> str:
    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC).isoformat()


def build_hook_actions(
    config: HookConfig,
    hook_payload: JsonObject,
    *,
    now: datetime | None = None,
) -> list[HookAction]:
    event_type = extract_event_type(hook_payload)
    occurred_at = extract_occurred_at(hook_payload) or utc_timestamp(now)
    actions = []
    if event_type in MESSAGE_EVENT_TYPES:
        actions.append(
            HookAction(
                endpoint="/api/v1/messages/ingest",
                payload=build_message_payload(
                    config,
                    hook_payload,
                    event_type=event_type,
                    occurred_at=occurred_at,
                ),
            )
        )
    actions.append(
        HookAction(
            endpoint="/api/v1/events/ingest",
            payload=build_event_payload(
                config,
                hook_payload,
                event_type=event_type,
                occurred_at=occurred_at,
            ),
        )
    )
    return actions


def build_message_payload(
    config: HookConfig,
    hook_payload: JsonObject,
    *,
    event_type: str,
    occurred_at: str,
) -> JsonObject:
    request_id = extract_request_id(hook_payload, event_type=event_type)
    role = "assistant" if event_type == "agent:end" else "user"
    direction = "OUTBOUND" if event_type == "agent:end" else "INBOUND"
    content = extract_content(hook_payload, role=role)
    parent_message_id = extract_parent_message_id(hook_payload)
    source = extract_source(config, hook_payload)
    return {
        "agent_uid": config.agent_uid,
        "idempotency_key": build_idempotency_key(config, source, request_id, event_type, role),
        "external_message_id": extract_external_message_id(hook_payload, request_id, role),
        "event_type": event_type,
        "source": source,
        "session_key": extract_session_key(config, hook_payload),
        "direction": direction,
        "role": role,
        "content": content,
        "request_id": request_id,
        "parent_message_id": parent_message_id,
        "occurred_at": occurred_at,
        "raw_payload": build_raw_payload(hook_payload, "message"),
    }


def build_event_payload(
    config: HookConfig,
    hook_payload: JsonObject,
    *,
    event_type: str,
    occurred_at: str,
) -> JsonObject:
    summary = first_string(
        hook_payload,
        "summary",
        "message",
        "text",
        "payload.summary",
        "payload.message",
    )
    return {
        "agent_uid": config.agent_uid,
        "event_type": event_type,
        "severity": first_string(hook_payload, "severity", "level", default="INFO"),
        "summary": summary or f"Hermes Gateway hook received: {event_type}",
        "occurred_at": occurred_at,
        "raw_payload": build_raw_payload(hook_payload, "event"),
    }


def build_raw_payload(hook_payload: JsonObject, mapped_as: str) -> JsonObject:
    return {
        "integration": "hermes_gateway_hook",
        "mapped_as": mapped_as,
        "hook_payload": hook_payload,
    }


def extract_event_type(hook_payload: JsonObject) -> str:
    return first_string(
        hook_payload,
        "event_type",
        "event",
        "type",
        "hook",
        "name",
        "payload.event_type",
        default="agent:hook",
    )


def extract_occurred_at(hook_payload: JsonObject) -> str | None:
    return first_string(
        hook_payload,
        "occurred_at",
        "timestamp",
        "created_at",
        "payload.occurred_at",
        "payload.timestamp",
    )


def extract_request_id(hook_payload: JsonObject, *, event_type: str) -> str:
    return first_string(
        hook_payload,
        "request_id",
        "run_id",
        "trace_id",
        "id",
        "payload.request_id",
        "payload.run_id",
        default=f"{event_type}:unknown",
    )


def extract_source(config: HookConfig, hook_payload: JsonObject) -> str:
    return first_string(
        hook_payload,
        "source",
        "platform",
        "adapter",
        "channel",
        "payload.source",
        "payload.platform",
        default=config.source,
    )


def extract_session_key(config: HookConfig, hook_payload: JsonObject) -> str:
    return first_string(
        hook_payload,
        "session_key",
        "session_id",
        "chat_id",
        "conversation_id",
        "session.id",
        "payload.session_key",
        "payload.session_id",
        default=config.session_key,
    )


def extract_external_message_id(hook_payload: JsonObject, request_id: str, role: str) -> str:
    return first_string(
        hook_payload,
        "external_message_id",
        "message_id",
        "payload.external_message_id",
        "payload.message_id",
        default=f"{request_id}:{role}",
    )


def extract_content(hook_payload: JsonObject, *, role: str) -> str:
    if role == "assistant":
        return first_string(
            hook_payload,
            "response",
            "output",
            "content",
            "message",
            "text",
            "payload.response",
            "payload.output",
            "payload.content",
            default="",
        )
    return first_string(
        hook_payload,
        "prompt",
        "input",
        "content",
        "message",
        "text",
        "payload.prompt",
        "payload.input",
        "payload.content",
        default="",
    )


def extract_parent_message_id(hook_payload: JsonObject) -> int | None:
    value = first_value(hook_payload, "parent_message_id", "payload.parent_message_id")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return None


def build_idempotency_key(
    config: HookConfig,
    source: str,
    request_id: str,
    event_type: str,
    role: str,
) -> str:
    return f"{config.agent_uid}:{source}:{request_id}:{event_type}:{role}"


def first_string(
    payload: Mapping[str, Any],
    *paths: str,
    default: str | None = None,
) -> str:
    value = first_value(payload, *paths)
    if isinstance(value, str) and value:
        return value
    if value is not None and not isinstance(value, (dict, list)):
        return str(value)
    if default is not None:
        return default
    return ""


def first_value(payload: Mapping[str, Any], *paths: str) -> Any:
    for path in paths:
        value = value_at_path(payload, path)
        if value is not None:
            return value
    return None


def value_at_path(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def run_hook_event(
    config: HookConfig,
    hook_payload: JsonObject,
    *,
    transport: Transport | None = None,
    now: datetime | None = None,
) -> list[JsonObject]:
    post_json = transport or UrlLibTransport(config).post_json
    headers = authorization_headers(config)
    results = []
    for action in build_hook_actions(config, hook_payload, now=now):
        response = post_json(action.endpoint, action.payload, headers)
        results.append({"endpoint": action.endpoint, "response": response})
    return results


def authorization_headers(config: HookConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.api_token}"}


class UrlLibTransport:
    def __init__(self, config: HookConfig, *, timeout_seconds: float = 10.0) -> None:
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
            raise HookHandlerError(message) from exc
        except URLError as exc:
            raise HookHandlerError(f"POST {path} failed: {exc.reason}") from exc


def decode_json_response(raw_body: bytes) -> JsonObject:
    try:
        value = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HookHandlerError("Expected JSON response from Hub") from exc
    if not isinstance(value, dict):
        raise HookHandlerError(f"Expected JSON object response from Hub: {value}")
    return value


def config_from_env(env: Mapping[str, str]) -> HookConfig:
    hostname = env.get("HERMES_HOOK_HOSTNAME", socket.gethostname())
    return HookConfig(
        hub_url=require_env(env, "HERMES_HUB_URL"),
        agent_uid=require_env(env, "HERMES_AGENT_UID"),
        api_token=require_env(env, "HERMES_API_TOKEN"),
        profile_name=env.get("HERMES_HOOK_PROFILE_NAME", hostname),
        hostname=hostname,
        ip_addr=env.get("HERMES_HOOK_IP_ADDR", DEFAULT_IP_ADDR),
        source=env.get("HERMES_HOOK_SOURCE", DEFAULT_SOURCE),
        session_key=env.get("HERMES_HOOK_SESSION_KEY", DEFAULT_SESSION_KEY),
    )


def require_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not value:
        raise HookHandlerError(f"Missing required environment variable: {name}")
    return value


def read_hook_payload(path: str | None, stdin_text: str) -> JsonObject:
    if path is not None:
        raw_text = Path(path).read_text(encoding="utf-8")
    else:
        raw_text = stdin_text
    try:
        value = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise HookHandlerError("Hook payload must be a JSON object") from exc
    if not isinstance(value, dict):
        raise HookHandlerError("Hook payload must be a JSON object")
    return value


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Forward Hermes Gateway hook payloads to Hub.")
    parser.add_argument("--dry-run", action="store_true", help="Print mapped Hub actions only.")
    parser.add_argument("--event-file", help="Read hook payload JSON from a file instead of stdin.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = config_from_env(os.environ)
        hook_payload = read_hook_payload(args.event_file, sys.stdin.read())
        if args.dry_run:
            output: Any = [action.as_dict() for action in build_hook_actions(config, hook_payload)]
        else:
            output = run_hook_event(config, hook_payload)
    except HookHandlerError as exc:
        print(f"Hermes Gateway hook failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
