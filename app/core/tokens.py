import hashlib
import secrets
from datetime import UTC, datetime

ENROLLMENT_TOKEN_PREFIX = "wps_enroll_"
API_TOKEN_PREFIX = "hub_api_"
AGENT_UID_PREFIX = "agent_"


def generate_enrollment_token() -> str:
    return f"{ENROLLMENT_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def generate_api_token() -> str:
    return f"{API_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def generate_agent_uid() -> str:
    today = datetime.now(UTC).strftime("%Y%m%d")
    return f"{AGENT_UID_PREFIX}{today}_{secrets.token_hex(4)}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
