"""Chapter 3 alignment fixes: UC4, UC5, UC25/30, UC31, UC33, UC38.

These cover the security / data-integrity hardening applied to make the code
match the thesis use-case descriptions.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from tests.conftest import auth_header


# ── UC4: change password ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_change_password_rejects_same_value(client: AsyncClient, user_token):
    res = await client.post(
        "/api/v1/auth/password/change",
        json={"current_password": "TestPassword1!", "new_password": "TestPassword1!"},
        headers=auth_header(user_token),
    )
    assert res.status_code == 400
    assert "different" in res.json()["detail"].lower()


# ── UC4: has_password exposed so the client can hide the form for Google ──────
@pytest.mark.asyncio
async def test_me_exposes_has_password(client: AsyncClient, user_token):
    res = await client.get("/api/v1/auth/me", headers=auth_header(user_token))
    assert res.status_code == 200
    assert res.json()["has_password"] is True


# ── UC5: single-use reset token ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_reset_token_is_single_use(client: AsyncClient, test_user):
    from app.services.auth_service import create_password_reset_token

    token = create_password_reset_token(test_user)
    r1 = await client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "new_password": "BrandNew1!"},
    )
    assert r1.status_code == 200
    # Replaying the same token after a successful reset must fail (fingerprint
    # changed because the password hash changed).
    r2 = await client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "new_password": "BrandNew2!"},
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_reset_token_without_fingerprint_rejected(client: AsyncClient, test_user):
    """A legacy token minted without a `pf` claim must be rejected outright."""
    from jose import jwt as jose_jwt

    from app.core.config import settings

    legacy = jose_jwt.encode(
        {
            "sub": str(test_user.id),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "password_reset",
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    res = await client.post(
        "/api/v1/auth/password/reset",
        json={"token": legacy, "new_password": "BrandNew1!"},
    )
    assert res.status_code == 400


# ── UC25/UC30: upload validation (pure unit, no Cloudinary call) ──────────────
JPEG_MAGIC = b"\xff\xd8\xff\xe0"


class _FakeUpload:
    def __init__(self, content_type, *, size=None, data=None):
        self.content_type = content_type
        self._data = data if data is not None else b"x" * (size or 0)

    async def read(self, n=-1):
        return self._data if n is None or n < 0 else self._data[:n]


@pytest.mark.nodb
@pytest.mark.asyncio
async def test_upload_rejects_bad_content_type():
    from app.services.cloudinary_service import upload_image

    with pytest.raises(HTTPException) as exc:
        await upload_image(_FakeUpload("text/plain", size=10))
    assert exc.value.status_code == 400


@pytest.mark.nodb
@pytest.mark.asyncio
async def test_upload_rejects_oversize_image():
    from app.services.cloudinary_service import MAX_IMAGE_BYTES, upload_image

    with pytest.raises(HTTPException) as exc:
        await upload_image(
            _FakeUpload("image/jpeg", data=JPEG_MAGIC + b"x" * MAX_IMAGE_BYTES)
        )
    assert exc.value.status_code == 413


@pytest.mark.nodb
@pytest.mark.asyncio
async def test_upload_rejects_spoofed_content_type():
    """A declared image/jpeg whose bytes are not an image must be rejected."""
    from app.services.cloudinary_service import upload_image

    with pytest.raises(HTTPException) as exc:
        await upload_image(_FakeUpload("image/jpeg", data=b"plain text, not an image"))
    assert exc.value.status_code == 400


@pytest.mark.nodb
@pytest.mark.asyncio
async def test_upload_accepts_real_jpeg(monkeypatch):
    from app.services import cloudinary_service

    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "upload",
        lambda contents, **k: {"secure_url": "https://cdn/x.jpg"},
    )
    url = await cloudinary_service.upload_image(
        _FakeUpload("image/jpeg", data=JPEG_MAGIC + b"0" * 64)
    )
    assert url == "https://cdn/x.jpg"


# ── UC31: cannot delete a used voucher ───────────────────────────────────────
@pytest.mark.asyncio
async def test_delete_used_voucher_returns_409(
    client: AsyncClient, db_session, admin_user, admin_token
):
    from app.models.voucher import Voucher

    voucher = Voucher(
        id=uuid.uuid4(),
        admin_id=admin_user.id,
        code=f"USED{uuid.uuid4().hex[:6]}",
        name="Used voucher",
        discount_value=10,
        valid_from=date.today(),
        valid_to=date.today() + timedelta(days=10),
        used_count=1,
    )
    db_session.add(voucher)
    await db_session.flush()

    res = await client.delete(
        f"/api/v1/vouchers/{voucher.id}", headers=auth_header(admin_token)
    )
    assert res.status_code == 409


# ── UC31: voucher usage total is not inflated by a cross join ────────────────
@pytest.mark.asyncio
async def test_voucher_usage_total_discount_not_inflated(
    client: AsyncClient, db_session, admin_user, admin_token
):
    """The discount total must sum only matched usage rows, not cross-join the
    whole bookings table (which would multiply the figure by the booking count)."""
    from app.core.security import hash_password
    from app.models.booking import Booking
    from app.models.user import User
    from app.models.voucher import Voucher
    from app.models.voucher_usage import VoucherUsage

    voucher = Voucher(
        id=uuid.uuid4(),
        admin_id=admin_user.id,
        code=f"SUM{uuid.uuid4().hex[:6]}",
        name="Sum voucher",
        discount_value=10,
        valid_from=date.today(),
        valid_to=date.today() + timedelta(days=10),
        used_count=2,
    )
    db_session.add(voucher)
    await db_session.flush()

    # Two distinct guests (uq_voucher_user) each redeem it once, $10 off each.
    for _ in range(2):
        guest = User(
            id=uuid.uuid4(),
            email=f"guest-{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hash_password("GuestPassword1!"),
            full_name="Guest",
            role="user",
            is_active=True,
        )
        db_session.add(guest)
        await db_session.flush()
        booking = Booking(
            id=uuid.uuid4(),
            user_id=guest.id,
            total_price=100,
            discount_amount=10,
            status="confirmed",
        )
        db_session.add(booking)
        await db_session.flush()
        db_session.add(
            VoucherUsage(
                id=uuid.uuid4(),
                voucher_id=voucher.id,
                user_id=guest.id,
                booking_id=booking.id,
            )
        )
    await db_session.flush()

    res = await client.get(
        f"/api/v1/vouchers/{voucher.id}/usages", headers=auth_header(admin_token)
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["total"] == 2
    # Exactly 2 × $10 — not inflated by the number of bookings in the table.
    assert body["meta"]["total_discount_amount"] == 20.0


# ── UC33: admin account guards ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_admin_cannot_self_delete(client: AsyncClient, admin_user, admin_token):
    res = await client.delete(
        f"/api/v1/admin/users/{admin_user.id}", headers=auth_header(admin_token)
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_admin_cannot_self_deactivate(client: AsyncClient, admin_user, admin_token):
    res = await client.patch(
        f"/api/v1/admin/users/{admin_user.id}",
        json={"is_active": False},
        headers=auth_header(admin_token),
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_another_admin(
    client: AsyncClient, db_session, admin_token
):
    from app.core.security import hash_password
    from app.models.user import User

    other = User(
        id=uuid.uuid4(),
        email=f"admin2-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("AdminPassword1!"),
        full_name="Other Admin",
        role="admin",
        is_active=True,
    )
    db_session.add(other)
    await db_session.flush()

    res = await client.patch(
        f"/api/v1/admin/users/{other.id}",
        json={"is_active": False},
        headers=auth_header(admin_token),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_deactivate_user_with_active_booking_requires_force(
    client: AsyncClient, db_session, test_user, admin_token
):
    from app.models.booking import Booking

    booking = Booking(
        id=uuid.uuid4(), user_id=test_user.id, total_price=100, status="confirmed"
    )
    db_session.add(booking)
    await db_session.flush()

    blocked = await client.patch(
        f"/api/v1/admin/users/{test_user.id}",
        json={"is_active": False},
        headers=auth_header(admin_token),
    )
    assert blocked.status_code == 409

    forced = await client.patch(
        f"/api/v1/admin/users/{test_user.id}?force=true",
        json={"is_active": False},
        headers=auth_header(admin_token),
    )
    assert forced.status_code == 200

    # Hard delete must stay blocked (no force) because it would cascade bookings.
    deleted = await client.delete(
        f"/api/v1/admin/users/{test_user.id}?force=true",
        headers=auth_header(admin_token),
    )
    assert deleted.status_code == 409


# ── UC33: deleting a voucher owner would cascade away usage history ──────────
@pytest.mark.asyncio
async def test_delete_user_with_vouchers_returns_409(
    client: AsyncClient, db_session, admin_token
):
    from app.core.security import hash_password
    from app.models.user import User
    from app.models.voucher import Voucher

    partner = User(
        id=uuid.uuid4(),
        email=f"partner-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("PartnerPassword1!"),
        full_name="Voucher Owner",
        role="partner",
        is_active=True,
    )
    db_session.add(partner)
    await db_session.flush()
    db_session.add(
        Voucher(
            id=uuid.uuid4(),
            admin_id=partner.id,
            code=f"OWN{uuid.uuid4().hex[:6]}",
            name="Owned voucher",
            discount_value=10,
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=10),
        )
    )
    await db_session.flush()

    res = await client.delete(
        f"/api/v1/admin/users/{partner.id}", headers=auth_header(admin_token)
    )
    assert res.status_code == 409
    assert "voucher" in res.json()["detail"].lower()


# ── UC38: loyalty tier threshold validation ──────────────────────────────────
def _tier(name, mn, mx):
    return {"name": name, "min_points": mn, "max_points": mx}


@pytest.mark.asyncio
async def test_tier_overlap_rejected(client: AsyncClient, admin_token):
    h = auth_header(admin_token)
    a = await client.post("/api/v1/admin/loyalty-tiers", json=_tier("LowA", 0, 499), headers=h)
    assert a.status_code == 201
    b = await client.post("/api/v1/admin/loyalty-tiers", json=_tier("MidA", 300, 999), headers=h)
    assert b.status_code == 409


@pytest.mark.asyncio
async def test_tier_max_below_min_rejected(client: AsyncClient, admin_token):
    res = await client.post(
        "/api/v1/admin/loyalty-tiers",
        json=_tier("BadRange", 1000, 500),
        headers=auth_header(admin_token),
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_non_top_tier_cannot_be_open_ended(client: AsyncClient, admin_token):
    h = auth_header(admin_token)
    # Single open-ended tier is fine (it is the top).
    a = await client.post("/api/v1/admin/loyalty-tiers", json=_tier("OpenLow", 0, 0), headers=h)
    assert a.status_code == 201
    # Adding a higher tier makes the open-ended one no longer the top → reject.
    b = await client.post("/api/v1/admin/loyalty-tiers", json=_tier("Higher", 100, 200), headers=h)
    assert b.status_code == 409


@pytest.mark.asyncio
async def test_valid_increasing_tiers_accepted(client: AsyncClient, admin_token):
    h = auth_header(admin_token)
    a = await client.post("/api/v1/admin/loyalty-tiers", json=_tier("Bronze2", 0, 499), headers=h)
    b = await client.post("/api/v1/admin/loyalty-tiers", json=_tier("Silver2", 500, 1499), headers=h)
    c = await client.post("/api/v1/admin/loyalty-tiers", json=_tier("Gold2", 1500, 0), headers=h)
    assert a.status_code == 201
    assert b.status_code == 201
    assert c.status_code == 201  # top tier may be open-ended
