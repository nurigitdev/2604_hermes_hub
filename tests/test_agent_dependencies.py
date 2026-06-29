from app.api.dependencies import extract_bearer_token


def test_extract_bearer_token_accepts_bearer_header() -> None:
    assert extract_bearer_token("Bearer hub_api_example") == "hub_api_example"


def test_extract_bearer_token_is_case_insensitive() -> None:
    assert extract_bearer_token("bearer hub_api_example") == "hub_api_example"


def test_extract_bearer_token_rejects_missing_header() -> None:
    assert extract_bearer_token(None) is None


def test_extract_bearer_token_rejects_header_without_separator() -> None:
    assert extract_bearer_token("Bearer") is None


def test_extract_bearer_token_rejects_wrong_scheme() -> None:
    assert extract_bearer_token("Basic hub_api_example") is None


def test_extract_bearer_token_rejects_empty_token() -> None:
    assert extract_bearer_token("Bearer   ") is None
