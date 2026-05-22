"""One-off cleanup: remove every flight-related booking row in the DB.

Drops in this order (FK-safe):
  1. payments rows whose booking has a flight item
  2. bookings rows that have a flight item (CASCADE deletes booking_item)
  3. flight_booking rows (now unreferenced)

Run inside the backend container:
  docker exec travel_backend python /app/scripts/clear_flight_bookings.py
"""
import asyncio
from sqlalchemy import text

from app.db.session import async_session_factory


async def main() -> None:
    async with async_session_factory() as s:
        deleted = {}
        deleted["payments"] = (await s.execute(text(
            "DELETE FROM payments WHERE booking_id IN ("
            "  SELECT DISTINCT booking_id FROM booking_item WHERE flight_booking_id IS NOT NULL"
            ")"
        ))).rowcount
        deleted["bookings"] = (await s.execute(text(
            "DELETE FROM bookings WHERE id IN ("
            "  SELECT DISTINCT booking_id FROM booking_item WHERE flight_booking_id IS NOT NULL"
            ")"
        ))).rowcount
        deleted["flight_booking"] = (await s.execute(text(
            "DELETE FROM flight_booking"
        ))).rowcount
        await s.commit()
        print("Deleted rows:", deleted)
        left_fb = (await s.execute(text("SELECT COUNT(*) FROM flight_booking"))).scalar()
        left_items = (await s.execute(text(
            "SELECT COUNT(*) FROM booking_item WHERE flight_booking_id IS NOT NULL"
        ))).scalar()
        print(f"Remaining flight_booking rows: {left_fb}")
        print(f"Remaining booking_item rows with flight_booking_id: {left_items}")


if __name__ == "__main__":
    asyncio.run(main())
