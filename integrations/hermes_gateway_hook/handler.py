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
MESSAGE_TYPE_PRE_LLM_CALL = 1
MESSAGE_TYPE_POST_LLM_CALL = 2
MESSAGE_TYPE_PRE_TOOL_CALL = 3
MESSAGE_TYPE_POST_TOOL_CALL = 4
MESSAGE_TYPE_NAME_BY_CODE = {
    MESSAGE_TYPE_PRE_LLM_CALL: "pre_llm_call",
    MESSAGE_TYPE_POST_LLM_CALL: "post_llm_call",
    MESSAGE_TYPE_PRE_TOOL_CALL: "pre_tool_call",
    MESSAGE_TYPE_POST_TOOL_CALL: "post_tool_call",
}
MESSAGE_TYPE_CODE_BY_NAME = {name: code for code, name in MESSAGE_TYPE_NAME_BY_CODE.items()}
LEGACY_EVENT_TYPE_CODE_BY_NAME = {
    "agent:start": MESSAGE_TYPE_PRE_LLM_CALL,
    "agent:end": MESSAGE_TYPE_POST_LLM_CALL,
    "message": MESSAGE_TYPE_PRE_LLM_CALL,
    "tool:start": MESSAGE_TYPE_PRE_TOOL_CALL,
    "tool:end": MESSAGE_TYPE_POST_TOOL_CALL,
}
MESSAGE_EVENT_TYPES = set(MESSAGE_TYPE_CODE_BY_NAME) | set(LEGACY_EVENT_TYPE_CODE_BY_NAME)
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
    message_type_code = extract_message_type_code(hook_payload, event_type=event_type)
    message_type_name = MESSAGE_TYPE_NAME_BY_CODE[message_type_code]
    role = role_for_message_type(message_type_code)
    direction = direction_for_message_type(message_type_code)
    content = extract_content(hook_payload, message_type_code=message_type_code, role=role)
    assistant_response = (
        extract_assistant_response(hook_payload)
        if message_type_code == MESSAGE_TYPE_POST_LLM_CALL
        else None
    )
    parent_message_id = extract_parent_message_id(hook_payload)
    source = extract_source(config, hook_payload)
    return {
        "agent_uid": config.agent_uid,
        "idempotency_key": build_idempotency_key(config, source, request_id, message_type_name),
        "external_message_id": extract_external_message_id(
            hook_payload,
            request_id,
            message_type_name,
        ),
        "event_type": event_type,
        "source": source,
        "session_key": extract_session_key(config, hook_payload),
        "direction": direction,
        "role": role,
        "message_type_code": message_type_code,
        "message_type": message_type_name,
        "content": content,
        "assistant_response": assistant_response,
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
        "user_message",
        "assistant_response",
        "tool_result",
        "message",
        "text",
        "payload.summary",
        "payload.user_message",
        "payload.assistant_response",
        "payload.tool_result",
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
    sanitized_payload, excluded_fields = sanitize_hook_payload(hook_payload)
    raw_payload = {
        "integration": "hermes_gateway_hook",
        "mapped_as": mapped_as,
        "hook_payload": sanitized_payload,
    }
    if excluded_fields:
        raw_payload["excluded_fields"] = excluded_fields
    return raw_payload


def extract_event_type(hook_payload: JsonObject) -> str:
    event_type = first_string(
        hook_payload,
        "event_type",
        "message_type",
        "event",
        "type",
        "hook",
        "name",
        "payload.event_type",
        "payload.message_type",
    )
    if event_type:
        return event_type
    return infer_observer_message_type(hook_payload) or "agent:hook"


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
        "turn_id",
        "request_id",
        "run_id",
        "trace_id",
        "id",
        "task_id",
        "payload.turn_id",
        "payload.request_id",
        "payload.run_id",
        "payload.task_id",
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


def extract_external_message_id(
    hook_payload: JsonObject,
    request_id: str,
    message_type_name: str,
) -> str:
    return first_string(
        hook_payload,
        "external_message_id",
        "message_id",
        "payload.external_message_id",
        "payload.message_id",
        default=f"{request_id}:{message_type_name}",
    )


def extract_content(hook_payload: JsonObject, *, message_type_code: int, role: str) -> str:
    if message_type_code == MESSAGE_TYPE_PRE_LLM_CALL:
        return first_string(
            hook_payload,
            "user_message",
            "prompt",
            "input",
            "content",
            "message",
            "text",
            "payload.user_message",
            "payload.prompt",
            "payload.input",
            "payload.content",
            default="",
        )
    if message_type_code == MESSAGE_TYPE_POST_LLM_CALL:
        return extract_assistant_response(hook_payload)
    if message_type_code == MESSAGE_TYPE_PRE_TOOL_CALL:
        return extract_tool_content(hook_payload, default="Tool call requested")
    if message_type_code == MESSAGE_TYPE_POST_TOOL_CALL:
        return extract_tool_content(hook_payload, default="Tool call completed")

    if role == "assistant":
        return extract_assistant_response(hook_payload)
    return first_string(
        hook_payload,
        "user_message",
        "prompt",
        "input",
        "content",
        "message",
        "text",
        "payload.user_message",
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


def extract_message_type_code(hook_payload: JsonObject, *, event_type: str) -> int:
    code = first_value(hook_payload, "message_type_code", "payload.message_type_code")
    if isinstance(code, int) and code in MESSAGE_TYPE_NAME_BY_CODE:
        return code
    if isinstance(code, str) and code.isdecimal():
        numeric_code = int(code)
        if numeric_code in MESSAGE_TYPE_NAME_BY_CODE:
            return numeric_code

    message_type = first_string(
        hook_payload,
        "message_type",
        "payload.message_type",
        "observer_type",
        "payload.observer_type",
    )
    if message_type in MESSAGE_TYPE_CODE_BY_NAME:
        return MESSAGE_TYPE_CODE_BY_NAME[message_type]
    if event_type in MESSAGE_TYPE_CODE_BY_NAME:
        return MESSAGE_TYPE_CODE_BY_NAME[event_type]
    if event_type in LEGACY_EVENT_TYPE_CODE_BY_NAME:
        return LEGACY_EVENT_TYPE_CODE_BY_NAME[event_type]

    inferred_message_type = infer_observer_message_type(hook_payload)
    if inferred_message_type is not None:
        return MESSAGE_TYPE_CODE_BY_NAME[inferred_message_type]
    return MESSAGE_TYPE_PRE_LLM_CALL


def infer_observer_message_type(hook_payload: JsonObject) -> str | None:
    if first_value(hook_payload, "user_message", "payload.user_message") is not None:
        return "pre_llm_call"
    if (
        first_value(
            hook_payload,
            "assistant_response",
            "llm_response",
            "response",
            "output",
            "payload.assistant_response",
            "payload.llm_response",
            "payload.response",
            "payload.output",
        )
        is not None
    ):
        return "post_llm_call"
    if first_value(hook_payload, "tool_result", "payload.tool_result") is not None:
        return "post_tool_call"
    if (
        first_value(
            hook_payload,
            "tool_name",
            "tool_call",
            "tool_arguments",
            "payload.tool_name",
            "payload.tool_call",
            "payload.tool_arguments",
        )
        is not None
    ):
        return "pre_tool_call"
    return None


def role_for_message_type(message_type_code: int) -> str:
    if message_type_code == MESSAGE_TYPE_POST_LLM_CALL:
        return "assistant"
    if message_type_code in {MESSAGE_TYPE_PRE_TOOL_CALL, MESSAGE_TYPE_POST_TOOL_CALL}:
        return "tool"
    return "user"


def direction_for_message_type(message_type_code: int) -> str:
    if message_type_code in {MESSAGE_TYPE_POST_LLM_CALL, MESSAGE_TYPE_PRE_TOOL_CALL}:
        return "OUTBOUND"
    return "INBOUND"


def extract_assistant_response(hook_payload: JsonObject) -> str:
    value = first_value(
        hook_payload,
        "assistant_response",
        "llm_response",
        "response",
        "output",
        "content",
        "message",
        "text",
        "payload.assistant_response",
        "payload.llm_response",
        "payload.response",
        "payload.output",
        "payload.content",
    )
    if value is None:
        return ""
    return stringify_json_value(value)


def extract_tool_content(hook_payload: JsonObject, *, default: str) -> str:
    tool_name = first_string(
        hook_payload,
        "tool_name",
        "tool",
        "payload.tool_name",
        "payload.tool",
    )
    tool_arguments = first_value(
        hook_payload,
        "tool_arguments",
        "arguments",
        "payload.tool_arguments",
        "payload.arguments",
    )
    tool_result = first_value(hook_payload, "tool_result", "result", "payload.tool_result")
    if tool_result is not None:
        return stringify_json_value(tool_result)
    if tool_name and tool_arguments is not None:
        return f"{tool_name}: {stringify_json_value(tool_arguments)}"
    if tool_name:
        return tool_name
    return first_string(hook_payload, "summary", "payload.summary", default=default)


def stringify_json_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def sanitize_hook_payload(hook_payload: JsonObject) -> tuple[JsonObject, list[str]]:
    sanitized_payload = dict(hook_payload)
    excluded_fields = []
    if "conversation_history" in sanitized_payload:
        del sanitized_payload["conversation_history"]
        excluded_fields.append("conversation_history")
    return sanitized_payload, excluded_fields


def build_idempotency_key(
    config: HookConfig,
    source: str,
    request_id: str,
    message_type_name: str,
) -> str:
    return f"{config.agent_uid}:{source}:{request_id}:{message_type_name}"


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
