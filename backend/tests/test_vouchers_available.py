"""Customer-facing available vouchers (UC_VIEW_VOUCHER)."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.booking import Booking, BookingStatus
from app.models.voucher import Voucher
from app.models.voucher_usage import VoucherUsage
from tests.conftest import auth_header


async def _mk(db, admin_id, *, code, status="active", days_to=30, days_from=-1,
             max_uses=5, used_count=0, budget=None, budget_used=0, guest_id=None):
    today = date.today()
    v = Voucher(
        id=uuid.uuid4(), admin_id=admin_id, code=code, name=f"{code}",
        discount_type="percentage", discount_value=10, min_order_value=0,
        max_uses=max_uses, used_count=used_count,
        valid_from=today + timedelta(days=days_from),
        valid_to=today + timedelta(days=days_to),
        status=status, budget=budget, budget_used=budget_used, guest_id=guest_id,
    )
    db.add(v)
    await db.flush()
    return v


@pytest.mark.asyncio
async def test_available_filters_correctly(client: AsyncClient, db_session, admin_user, test_user, user_token):
    ok = await _mk(db_session, admin_user.id, code="OKAY")
    await _mk(db_session, admin_user.id, code="EXPIRED", days_to=-1)            # past valid_to
    await _mk(db_session, admin_user.id, code="DISABLED", status="disabled")    # not active
    await _mk(db_session, admin_user.id, code="EXHAUSTED", max_uses=2, used_count=2)
    await _mk(db_session, admin_user.id, code="NOBUDGET", budget=50, budget_used=50)
    await _mk(db_session, admin_user.id, code="OTHERGUEST", guest_id=admin_user.id)  # reserved for another real user

    # Already used by this user → excluded.
    used = await _mk(db_session, admin_user.id, code="USED")
    booking = Booking(id=uuid.uuid4(), user_id=test_user.id, total_price=Decimal("50"), status=BookingStatus.confirmed.value)
    db_session.add(booking)
    await db_session.flush()
    db_session.add(VoucherUsage(voucher_id=used.id, user_id=test_user.id, booking_id=booking.id))
    await db_session.flush()

    res = await client.get("/api/v1/vouchers/available", headers=auth_header(user_token))
    assert res.status_code == 200
    codes = {v["code"] for v in res.json()}
    assert "OKAY" in codes
    assert codes.isdisjoint({"EXPIRED", "DISABLED", "EXHAUSTED", "NOBUDGET", "OTHERGUEST", "USED"})


@pytest.mark.asyncio
async def test_available_response_is_public_shape(client: AsyncClient, db_session, admin_user, user_token):
    await _mk(db_session, admin_user.id, code="PUB", budget=1000, budget_used=10)
    res = await client.get("/api/v1/vouchers/available", headers=auth_header(user_token))
    assert res.status_code == 200
    item = next(v for v in res.json() if v["code"] == "PUB")
    # Public schema must NOT leak internal fields.
    assert "budget" not in item and "budget_used" not in item and "admin_id" not in item
    assert {"code", "name", "discount_type", "discount_value"} <= set(item)


@pytest.mark.asyncio
async def test_available_guest_specific_visible_to_owner(client: AsyncClient, db_session, admin_user, test_user, user_token):
    await _mk(db_session, admin_user.id, code="MINE", guest_id=test_user.id)
    res = await client.get("/api/v1/vouchers/available", headers=auth_header(user_token))
    assert "MINE" in {v["code"] for v in res.json()}
