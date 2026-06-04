"""Unit tests for partner-room cancellation refund policy.

Partner-owned rooms carry a LiteAPI-style deadline policy snapshotted onto the
BookingItem at booking time. These cover the three branches of
``_local_room_refund`` plus the pro-rata share used for multi-item bookings.
No DB needed — the helpers only read attributes off in-memory objects.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.booking import Booking, BookingStatus
from app.models.booking_item import BookingItem, BookingItemStatus, BookingItemType
from app.services.booking_service import _item_refund_share, _local_room_refund


def _booking(total, items):
    b = Booking(user_id=None, total_price=Decimal(str(total)), status=BookingStatus.confirmed.value)
    b.items = items
    return b


def _room_item(subtotal, *, refundable=True, deadline=None, fee_pct=100):
    return BookingItem(
        item_type=BookingItemType.room.value,
        room_id="00000000-0000-0000-0000-000000000001",
        unit_price=Decimal(str(subtotal)),
        subtotal=Decimal(str(subtotal)),
        quantity=1,
        status=BookingItemStatus.confirmed.value,
        refundable=refundable,
        cancellation_deadline=deadline,
        cancellation_fee_percent=fee_pct,
    )


@pytest.mark.nodb
def test_refund_full_before_deadline():
    future = datetime.now(timezone.utc) + timedelta(days=3)
    item = _room_item(200, deadline=future, fee_pct=100)
    booking = _booking(200, [item])
    refund, fee = _local_room_refund(booking, item)
    assert refund == 200.0
    assert fee == 0.0


@pytest.mark.nodb
def test_refund_partial_after_deadline():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    item = _room_item(200, deadline=past, fee_pct=25)
    booking = _booking(200, [item])
    refund, fee = _local_room_refund(booking, item)
    assert fee == 50.0  # 25% of 200
    assert refund == 150.0


@pytest.mark.nodb
def test_non_refundable_room_keeps_everything():
    item = _room_item(200, refundable=False)
    booking = _booking(200, [item])
    refund, fee = _local_room_refund(booking, item)
    assert refund == 0.0
    assert fee == 200.0


@pytest.mark.nodb
def test_no_deadline_is_treated_as_free_cancel():
    item = _room_item(200, deadline=None)
    booking = _booking(200, [item])
    refund, fee = _local_room_refund(booking, item)
    assert refund == 200.0
    assert fee == 0.0


@pytest.mark.nodb
def test_multi_item_share_prorates_by_subtotal():
    # Two lines: room 300 + tour 100 of a 440-total booking (incl. taxes).
    room = _room_item(300, deadline=datetime.now(timezone.utc) + timedelta(days=2))
    tour = _room_item(100)
    booking = _booking(440, [room, tour])
    # Room's share = 440 * 300/400 = 330.
    assert _item_refund_share(booking, room) == 330.0
    refund, fee = _local_room_refund(booking, room)
    assert refund == 330.0
    assert fee == 0.0
