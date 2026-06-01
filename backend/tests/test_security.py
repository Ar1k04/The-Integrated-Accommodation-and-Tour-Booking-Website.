"""Unit tests cho app/core/security.py (pure logic — KHÔNG cần DB).

Phủ băm mật khẩu (bcrypt + SHA-256 prehash) và JWT (access/refresh) — nền tảng
của toàn bộ auth. SECRET_KEY mặc định rỗng trong môi trường không có .env nên
ta monkeypatch một key cố định để token round-trip ổn định.

Test IDs: UT-BE-SEC-01..NN.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core import security
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

pytestmark = pytest.mark.nodb


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    # Khoá ký cố định để test deterministic, độc lập với .env.
    monkeypatch.setattr(settings, "SECRET_KEY", "unit-test-secret-key")
    monkeypatch.setattr(settings, "ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15)
    monkeypatch.setattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7)


# ── Password hashing ─────────────────────────────────────────────────────────
class TestPasswordHashing:
    def test_hash_then_verify_roundtrip(self):
        hashed = hash_password("TestPassword1!")
        assert hashed != "TestPassword1!"  # không lưu plaintext
        assert verify_password("TestPassword1!", hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("TestPassword1!")
        assert verify_password("WrongPassword", hashed) is False

    def test_hash_is_salted_unique_each_call(self):
        # Cùng mật khẩu nhưng salt khác → hash khác nhau.
        assert hash_password("samepw") != hash_password("samepw")

    def test_very_long_password_supported(self):
        # SHA-256 prehash cho phép mật khẩu dài hơn giới hạn 72 byte của bcrypt.
        long_pw = "a" * 200
        hashed = hash_password(long_pw)
        assert verify_password(long_pw, hashed) is True

    def test_unicode_password_supported(self):
        pw = "Mật_khẩu_Tiếng_Việt_😀"
        assert verify_password(pw, hash_password(pw)) is True


# ── Access / refresh token creation ──────────────────────────────────────────
class TestTokenCreation:
    def test_access_token_roundtrip_with_uuid_subject(self):
        uid = uuid.uuid4()
        token = create_access_token(uid)
        payload = decode_token(token)
        assert payload["sub"] == str(uid)
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_access_token_merges_extra_claims(self):
        token = create_access_token("user-1", extra={"role": "admin"})
        payload = decode_token(token)
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_refresh_token_has_jti_and_type(self):
        token = create_refresh_token("user-1")
        payload = decode_token(token)
        assert payload["type"] == "refresh"
        assert "jti" in payload  # cho phép blacklist khi logout

    def test_two_refresh_tokens_have_distinct_jti(self):
        p1 = decode_token(create_refresh_token("u"))
        p2 = decode_token(create_refresh_token("u"))
        assert p1["jti"] != p2["jti"]

    def test_access_expires_sooner_than_refresh(self):
        a = decode_token(create_access_token("u"))
        r = decode_token(create_refresh_token("u"))
        assert a["exp"] < r["exp"]


# ── decode_token error handling ──────────────────────────────────────────────
class TestDecodeToken:
    def test_tampered_signature_raises_value_error(self):
        token = create_access_token("user-1")
        tampered = token[:-3] + ("abc" if not token.endswith("abc") else "xyz")
        with pytest.raises(ValueError):
            decode_token(tampered)

    def test_wrong_secret_raises_value_error(self, monkeypatch):
        token = create_access_token("user-1")
        monkeypatch.setattr(settings, "SECRET_KEY", "a-different-secret")
        with pytest.raises(ValueError):
            decode_token(token)

    def test_expired_token_raises_value_error(self):
        # Token đã hết hạn (exp ở quá khứ) → decode_token bọc JWTError thành ValueError.
        expired = jwt.encode(
            {
                "sub": "user-1",
                "type": "access",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(ValueError):
            decode_token(expired)

    def test_garbage_string_raises_value_error(self):
        with pytest.raises(ValueError):
            decode_token("not-a-jwt")
