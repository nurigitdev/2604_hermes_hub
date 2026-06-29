from app.core.tokens import (
    AGENT_UID_PREFIX,
    API_TOKEN_PREFIX,
    ENROLLMENT_TOKEN_PREFIX,
    generate_agent_uid,
    generate_api_token,
    generate_enrollment_token,
    hash_token,
)


def test_generate_enrollment_token_uses_expected_prefix() -> None:
    token = generate_enrollment_token()

    assert token.startswith(ENROLLMENT_TOKEN_PREFIX)


def test_generate_enrollment_token_uses_random_value() -> None:
    assert generate_enrollment_token() != generate_enrollment_token()


def test_generate_api_token_uses_expected_prefix() -> None:
    token = generate_api_token()

    assert token.startswith(API_TOKEN_PREFIX)


def test_generate_api_token_uses_random_value() -> None:
    assert generate_api_token() != generate_api_token()


def test_generate_agent_uid_uses_expected_prefix() -> None:
    agent_uid = generate_agent_uid()

    assert agent_uid.startswith(AGENT_UID_PREFIX)


def test_generate_agent_uid_uses_random_value() -> None:
    assert generate_agent_uid() != generate_agent_uid()


def test_hash_token_is_deterministic_and_does_not_store_plaintext() -> None:
    token = "wps_enroll_example"
    token_hash = hash_token(token)

    assert token_hash == hash_token(token)
    assert token not in token_hash
    assert len(token_hash) == 64
