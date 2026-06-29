import base64
import hashlib
import hmac


def create_session_token(*, user_id: int, secret_key: str) -> str:
    payload = str(user_id).encode("utf-8")
    payload_text = base64.urlsafe_b64encode(payload).decode("ascii")
    signature = sign_payload(payload_text=payload_text, secret_key=secret_key)
    return f"{payload_text}.{signature}"


def verify_session_token(token: str, *, secret_key: str) -> int | None:
    try:
        payload_text, signature = token.split(".", 1)
    except ValueError:
        return None

    expected_signature = sign_payload(payload_text=payload_text, secret_key=secret_key)
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = base64.urlsafe_b64decode(payload_text.encode("ascii")).decode("utf-8")
        return int(payload)
    except (ValueError, UnicodeDecodeError):
        return None


def sign_payload(*, payload_text: str, secret_key: str) -> str:
    digest = hmac.new(
        secret_key.encode("utf-8"),
        payload_text.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")
