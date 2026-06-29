import base64

from app.core.session import create_session_token, sign_payload, verify_session_token


def test_session_token_round_trip() -> None:
    token = create_session_token(user_id=123, secret_key="test-secret")

    assert verify_session_token(token, secret_key="test-secret") == 123


def test_verify_session_token_rejects_malformed_token() -> None:
    assert verify_session_token("not-a-token", secret_key="test-secret") is None


def test_verify_session_token_rejects_tampered_signature() -> None:
    token = create_session_token(user_id=123, secret_key="test-secret")
    payload, _signature = token.split(".", 1)

    assert verify_session_token(f"{payload}.tampered", secret_key="test-secret") is None


def test_verify_session_token_rejects_wrong_secret() -> None:
    token = create_session_token(user_id=123, secret_key="test-secret")

    assert verify_session_token(token, secret_key="wrong-secret") is None


def test_verify_session_token_rejects_non_integer_payload() -> None:
    payload = base64.urlsafe_b64encode(b"not-int").decode("ascii")
    signature = sign_payload(payload_text=payload, secret_key="test-secret")

    assert verify_session_token(f"{payload}.{signature}", secret_key="test-secret") is None
