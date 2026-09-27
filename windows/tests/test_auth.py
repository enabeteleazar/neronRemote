from __future__ import annotations

from auth import is_valid_token


def test_rejects_missing_header():
    assert is_valid_token("secret", None) is False


def test_rejects_header_without_bearer_prefix():
    assert is_valid_token("secret", "secret") is False


def test_rejects_wrong_token():
    assert is_valid_token("secret", "Bearer wrong") is False


def test_accepts_matching_token():
    assert is_valid_token("secret", "Bearer secret") is True
