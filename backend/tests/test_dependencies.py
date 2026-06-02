"""Unit tests cho app/core/dependencies.py (pure — KHÔNG cần DB).

Kiểm tra các nhánh KHÔNG chạm DB của get_current_user (thiếu/sai/nhầm loại
token) và toàn bộ logic phân quyền require_staff/require_admin (nhận sẵn user).
Nhánh tra cứu user trong DB được phủ gián tiếp bởi các route test.
Test IDs: UT-BE-DEP-01..NN.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.config import settings
from app.core.dependencies import get_current_user, require_admin, require_staff
from app.core.security import create_refresh_token

pytestmark = pytest.mark.nodb


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "unit-test-secret")
    monkeypatch.setattr(settings, "ALGORITHM", "HS256")


class _FakeUser:
    def __init__(self, role="user", is_active=True, partner_status=None):
        self.role = role
        self.is_active = is_active
        # Partners are gated by approval; default approved for non-pending cases.
        self.partner_status = partner_status if partner_status is not None else (
            "approved" if role == "partner" else None
        )
        self.id = uuid.uuid4()


class TestGetCurrentUserNoDbBranches:
    async def test_no_token_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(db=None, access_token=None, authorization=None)
        assert exc.value.status_code == 401

    async def test_malformed_token_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(db=None, access_token=None, authorization="Bearer not-a-jwt")
        assert exc.value.status_code == 401

    async def test_refresh_token_rejected_as_access(self):
        refresh = create_refresh_token("user-1")
        with pytest.raises(HTTPException) as exc:
            await get_current_user(db=None, access_token=refresh, authorization=None)
        assert exc.value.status_code == 401

    async def test_token_without_subject_401(self):
        token = jwt.encode(
            {"type": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            await get_current_user(db=None, access_token=token, authorization=None)
        assert exc.value.status_code == 401


class TestRoleGuards:
    async def test_require_staff_blocks_regular_user(self):
        with pytest.raises(HTTPException) as exc:
            await require_staff(_FakeUser(role="user"))
        assert exc.value.status_code == 403

    async def test_require_staff_allows_partner_and_admin(self):
        assert (await require_staff(_FakeUser(role="partner"))).role == "partner"
        assert (await require_staff(_FakeUser(role="admin"))).role == "admin"

    async def test_require_staff_blocks_unapproved_partner(self):
        # Pending/rejected partners can log in but cannot use staff endpoints.
        for status_val in ("pending", "rejected"):
            with pytest.raises(HTTPException) as exc:
                await require_staff(_FakeUser(role="partner", partner_status=status_val))
            assert exc.value.status_code == 403

    async def test_require_admin_blocks_partner(self):
        with pytest.raises(HTTPException) as exc:
            await require_admin(_FakeUser(role="partner"))
        assert exc.value.status_code == 403

    async def test_require_admin_allows_admin(self):
        assert (await require_admin(_FakeUser(role="admin"))).role == "admin"
