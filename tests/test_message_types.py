import pytest

from app.core.message_types import (
    InvalidMessageTypeError,
    infer_message_type_code,
    message_type_name,
    normalize_message_type_code,
)


def test_message_type_name_returns_known_name() -> None:
    assert message_type_name(1) == "pre_llm_call"


def test_message_type_name_rejects_unknown_code() -> None:
    with pytest.raises(InvalidMessageTypeError, match="Unsupported message type code"):
        message_type_name(9)


def test_normalize_message_type_code_uses_explicit_code() -> None:
    assert normalize_message_type_code(message_type_code=3) == 3


def test_normalize_message_type_code_rejects_unknown_code() -> None:
    with pytest.raises(InvalidMessageTypeError, match="Unsupported message type code"):
        normalize_message_type_code(message_type_code=9)


def test_normalize_message_type_code_rejects_conflict() -> None:
    with pytest.raises(InvalidMessageTypeError, match="Conflicting message type"):
        normalize_message_type_code(message_type_code=1, message_type="post_llm_call")


def test_infer_message_type_code_supports_message_type_name() -> None:
    assert infer_message_type_code(message_type="post_tool_call") == 4


def test_infer_message_type_code_rejects_unknown_name() -> None:
    with pytest.raises(InvalidMessageTypeError, match="Unsupported message type"):
        infer_message_type_code(message_type="unknown")


def test_infer_message_type_code_supports_event_type_name() -> None:
    assert infer_message_type_code(event_type="pre_tool_call") == 3


def test_infer_message_type_code_supports_legacy_event_type() -> None:
    assert infer_message_type_code(event_type="agent:end") == 2


def test_infer_message_type_code_falls_back_when_event_type_is_unknown() -> None:
    assert infer_message_type_code(event_type="agent:custom", role="assistant") == 2


def test_infer_message_type_code_uses_tool_direction() -> None:
    assert infer_message_type_code(role="tool", direction="OUTBOUND") == 3
    assert infer_message_type_code(role="tool", direction="INBOUND") == 4


def test_infer_message_type_code_uses_assistant_or_outbound_as_post_llm() -> None:
    assert infer_message_type_code(role="assistant") == 2
    assert infer_message_type_code(direction="OUTBOUND") == 2


def test_infer_message_type_code_defaults_to_pre_llm() -> None:
    assert infer_message_type_code() == 1
