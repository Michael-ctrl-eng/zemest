"""Tests for security utilities — JWT, password hashing, webhook signature."""
import pytest

from app.utils.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestSecurity:

    def test_password_hash_and_verify(self):
        hashed = hash_password("mysecretpassword")
        assert hashed != "mysecretpassword"
        assert verify_password("mysecretpassword", hashed) is True

    def test_password_wrong_verify(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_create_and_decode_token(self):
        token = create_access_token({"sub": "user-123", "role": "admin"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"

    def test_decode_invalid_token(self):
        payload = decode_token("invalid.token.here")
        assert payload is None

    def test_decode_empty_token(self):
        payload = decode_token("")
        assert payload is None

    def test_token_contains_expiry(self):
        token = create_access_token({"sub": "test"})
        payload = decode_token(token)
        assert "exp" in payload
