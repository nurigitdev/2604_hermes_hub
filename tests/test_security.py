from app.core.security import hash_password, verify_password


def test_hash_password_does_not_store_plaintext() -> None:
    password_hash = hash_password("change-me-admin-password")

    assert "change-me-admin-password" not in password_hash
    assert password_hash.startswith("pbkdf2_sha256$")


def test_hash_password_uses_random_salt() -> None:
    first_hash = hash_password("change-me-admin-password")
    second_hash = hash_password("change-me-admin-password")

    assert first_hash != second_hash


def test_verify_password_accepts_matching_password() -> None:
    password_hash = hash_password("change-me-admin-password")

    assert verify_password("change-me-admin-password", password_hash)


def test_verify_password_rejects_wrong_password() -> None:
    password_hash = hash_password("change-me-admin-password")

    assert not verify_password("wrong-password", password_hash)


def test_verify_password_rejects_malformed_hash() -> None:
    assert not verify_password("change-me-admin-password", "not-a-valid-hash")
