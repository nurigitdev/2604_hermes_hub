from typing import Final

MESSAGE_TYPE_PRE_LLM_CALL: Final = 1
MESSAGE_TYPE_POST_LLM_CALL: Final = 2
MESSAGE_TYPE_PRE_TOOL_CALL: Final = 3
MESSAGE_TYPE_POST_TOOL_CALL: Final = 4

MESSAGE_TYPE_NAME_BY_CODE: Final = {
    MESSAGE_TYPE_PRE_LLM_CALL: "pre_llm_call",
    MESSAGE_TYPE_POST_LLM_CALL: "post_llm_call",
    MESSAGE_TYPE_PRE_TOOL_CALL: "pre_tool_call",
    MESSAGE_TYPE_POST_TOOL_CALL: "post_tool_call",
}
MESSAGE_TYPE_CODE_BY_NAME: Final = {
    name: code for code, name in MESSAGE_TYPE_NAME_BY_CODE.items()
}

LEGACY_EVENT_TYPE_CODE_BY_NAME: Final = {
    "agent:start": MESSAGE_TYPE_PRE_LLM_CALL,
    "agent:end": MESSAGE_TYPE_POST_LLM_CALL,
    "message": MESSAGE_TYPE_PRE_LLM_CALL,
    "tool:start": MESSAGE_TYPE_PRE_TOOL_CALL,
    "tool:end": MESSAGE_TYPE_POST_TOOL_CALL,
}


class InvalidMessageTypeError(ValueError):
    pass


def message_type_name(message_type_code: int) -> str:
    try:
        return MESSAGE_TYPE_NAME_BY_CODE[message_type_code]
    except KeyError as exc:
        message = f"Unsupported message type code: {message_type_code}"
        raise InvalidMessageTypeError(message) from exc


def normalize_message_type_code(
    *,
    message_type_code: int | None = None,
    message_type: str | None = None,
    event_type: str | None = None,
    role: str | None = None,
    direction: str | None = None,
) -> int:
    inferred_code = infer_message_type_code(
        message_type=message_type,
        event_type=event_type,
        role=role,
        direction=direction,
    )

    if message_type_code is None:
        return inferred_code
    if message_type_code not in MESSAGE_TYPE_NAME_BY_CODE:
        raise InvalidMessageTypeError(f"Unsupported message type code: {message_type_code}")
    if message_type is not None and inferred_code != message_type_code:
        raise InvalidMessageTypeError(
            f"Conflicting message type values: {message_type_code} and {message_type}"
        )
    return message_type_code


def infer_message_type_code(
    *,
    message_type: str | None = None,
    event_type: str | None = None,
    role: str | None = None,
    direction: str | None = None,
) -> int:
    if message_type:
        try:
            return MESSAGE_TYPE_CODE_BY_NAME[message_type]
        except KeyError as exc:
            raise InvalidMessageTypeError(f"Unsupported message type: {message_type}") from exc

    if event_type:
        if event_type in MESSAGE_TYPE_CODE_BY_NAME:
            return MESSAGE_TYPE_CODE_BY_NAME[event_type]
        if event_type in LEGACY_EVENT_TYPE_CODE_BY_NAME:
            return LEGACY_EVENT_TYPE_CODE_BY_NAME[event_type]

    normalized_role = (role or "").lower()
    normalized_direction = (direction or "").upper()
    if normalized_role == "tool":
        if normalized_direction == "OUTBOUND":
            return MESSAGE_TYPE_PRE_TOOL_CALL
        return MESSAGE_TYPE_POST_TOOL_CALL
    if normalized_role == "assistant" or normalized_direction == "OUTBOUND":
        return MESSAGE_TYPE_POST_LLM_CALL
    return MESSAGE_TYPE_PRE_LLM_CALL
