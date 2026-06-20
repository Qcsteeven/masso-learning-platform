"""Unit tests for app.core.security — no DB, no Redis, no external calls."""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)

# ── Password hashing ──────────────────────────────────────────────────────────

def test_hash_and_verify_correct_password() -> None:
    plain = "sup3r-s3cr3t!"
    hashed = hash_password(plain)
    assert hashed != plain, "Hash must differ from plaintext"
    assert verify_password(plain, hashed) is True


def test_verify_wrong_password_returns_false() -> None:
    hashed = hash_password("correct_password")
    assert verify_password("wrong_password", hashed) is False


def test_different_hashes_for_same_password() -> None:
    """bcrypt uses a per-call random salt so two hashes of the same password differ."""
    p = "same_password"
    assert hash_password(p) != hash_password(p)


# ── JWT access token ──────────────────────────────────────────────────────────

def test_create_and_decode_access_token() -> None:
    user_id = "11111111-1111-1111-1111-111111111111"
    roles = ["admin", "teacher"]
    token = create_access_token(user_id, roles)
    payload = decode_access_token(token)

    assert payload["sub"] == user_id
    assert payload["roles"] == roles
    assert "jti" in payload
    assert "exp" in payload


def test_decode_expired_token_raises_401() -> None:
    token = create_access_token(
        "22222222-2222-2222-2222-222222222222",
        ["student"],
        expires_delta=timedelta(seconds=-1),  # already expired
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_decode_tampered_token_raises_401() -> None:
    token = create_access_token("some-id", ["student"])
    # Flip the last character of the signature
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(tampered)
    assert exc_info.value.status_code == 401


def test_decode_garbage_token_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("not.a.jwt")
    assert exc_info.value.status_code == 401


def test_access_token_payload_contains_sub_and_roles() -> None:
    uid = "33333333-3333-3333-3333-333333333333"
    roles = ["methodist"]
    payload = decode_access_token(create_access_token(uid, roles))
    assert payload["sub"] == uid
    assert payload["roles"] == roles


# ── Refresh token ─────────────────────────────────────────────────────────────

def test_create_refresh_token_is_non_empty_string() -> None:
    rt = create_refresh_token()
    assert isinstance(rt, str)
    assert len(rt) >= 32  # URL-safe base64 of 32 bytes


def test_refresh_tokens_are_unique() -> None:
    tokens = {create_refresh_token() for _ in range(20)}
    assert len(tokens) == 20, "Each refresh token must be unique"
