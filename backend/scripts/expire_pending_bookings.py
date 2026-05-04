"""One-shot script to cancel stale pending bookings whose checkout TTL has expired.

Run after the 15-min soft-lock window to free DB inventory held by abandoned checkouts.

Usage (Docker):
    docker exec travel_backend python -m scripts.expire_pending_bookings

Safe to run multiple times (idempotent — skips already-cancelled bookings).
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.booking import Booking, BookingStatus
from app.models.booking_item import BookingItem
from app.models.flight_booking import FlightBooking
from app.services.booking_service import cancel_booking

STALE_AFTER_MINUTES = 20  # slightly larger than the 15-min lock TTL

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def main() -> None:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=STALE_AFTER_MINUTES)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking)
            .options(
                selectinload(Booking.items).selectinload(BookingItem.flight_booking),
                selectinload(Booking.items).selectinload(BookingItem.room),
            )
            .where(
                Booking.status == BookingStatus.pending.value,
                Booking.created_at < cutoff,
            )
        )
        stale = result.scalars().all()

        if not stale:
            print("No stale pending bookings found.")
            return

        cancelled = 0
        for booking in stale:
            try:
                await cancel_booking(db, booking, redis=None)
                cancelled += 1
                print(f"  Cancelled booking {booking.id} (created {booking.created_at})")
            except Exception as exc:
                print(f"  ERROR cancelling {booking.id}: {exc}")

        await db.commit()
        print(f"\nDone. Cancelled {cancelled}/{len(stale)} stale pending bookings.")


if __name__ == "__main__":
    asyncio.run(main())
