from app.core.tokens import ENROLLMENT_TOKEN_PREFIX, generate_enrollment_token, hash_token


def test_generate_enrollment_token_uses_expected_prefix() -> None:
    token = generate_enrollment_token()

    assert token.startswith(ENROLLMENT_TOKEN_PREFIX)


def test_generate_enrollment_token_uses_random_value() -> None:
    assert generate_enrollment_token() != generate_enrollment_token()


def test_hash_token_is_deterministic_and_does_not_store_plaintext() -> None:
    token = "wps_enroll_example"
    token_hash = hash_token(token)

    assert token_hash == hash_token(token)
    assert token not in token_hash
    assert len(token_hash) == 64
