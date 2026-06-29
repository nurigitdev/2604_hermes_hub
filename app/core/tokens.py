import hashlib
import secrets

ENROLLMENT_TOKEN_PREFIX = "wps_enroll_"


def generate_enrollment_token() -> str:
    return f"{ENROLLMENT_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
