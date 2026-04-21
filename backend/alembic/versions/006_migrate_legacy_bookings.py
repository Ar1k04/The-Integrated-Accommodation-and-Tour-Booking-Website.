"""migrate legacy booking/tour_booking/promo_code data into new schema

Revision ID: 006
Revises: 005
Create Date: 2026-04-21

Sprint 1, step 2. This migration reshapes existing rows to live under the
polymorphic booking/booking_item model without losing data:

  1. bookings.{room_id,check_in,check_out} become nullable; new columns
     voucher_id / discount_amount / points_earned / points_redeemed added.
  2. Every row in `bookings` gets a matching `booking_item` (item_type='room').
  3. Every row in `promo_codes` is copied into `vouchers` (owned by the first
     superadmin/admin/user we can find).
  4. `tour_bookings` rows are projected onto `tour_schedule` (aggregated),
     `bookings` (new rows), and `booking_item` (item_type='tour').
  5. Users with `loyalty_points > 0` get one `loyalty_transaction` row
     (type='adjust') as a backfill audit entry.

Downgrade best-effort: removes all rows created by this migration that can
be unambiguously identified. NEW bookings created via the refactored API
after the upgrade will be lost on downgrade (tour/flight items cannot be
reconstructed into the old tour_bookings table); this is documented and
accepted.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Evolve bookings table schema -------------------------------
    op.add_column("bookings", sa.Column("voucher_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("bookings", sa.Column("discount_amount", sa.Numeric(10, 2), server_default="0", nullable=False))
    op.add_column("bookings", sa.Column("points_earned", sa.Integer(), server_default="0", nullable=False))
    op.add_column("bookings", sa.Column("points_redeemed", sa.Integer(), server_default="0", nullable=False))
    op.create_foreign_key(
        "fk_bookings_voucher_id", "bookings", "vouchers",
        ["voucher_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_bookings_voucher_id", "bookings", ["voucher_id"])

    op.alter_column("bookings", "room_id", nullable=True)
    op.alter_column("bookings", "check_in", nullable=True)
    op.alter_column("bookings", "check_out", nullable=True)

    # --- 2. bookings → booking_item (item_type='room') -----------------
    op.execute(
        """
        INSERT INTO booking_item
            (booking_id, item_type, room_id, check_in, check_out,
             unit_price, subtotal, quantity, status)
        SELECT
            b.id,
            'room',
            b.room_id,
            b.check_in,
            b.check_out,
            CASE WHEN (b.check_out - b.check_in) > 0
                 THEN b.total_price / (b.check_out - b.check_in)
                 ELSE b.total_price
            END,
            b.total_price,
            COALESCE(b.guests_count, 1),
            b.status
        FROM bookings b
        WHERE b.room_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM booking_item bi WHERE bi.booking_id = b.id
          )
        """
    )

    # --- 3. promo_codes → vouchers -------------------------------------
    # Pick a real admin to own the legacy vouchers; if none exist, skip.
    op.execute(
        """
        DO $$
        DECLARE
            owner_id UUID;
        BEGIN
            SELECT id INTO owner_id FROM users WHERE role = 'superadmin' ORDER BY created_at LIMIT 1;
            IF owner_id IS NULL THEN
                SELECT id INTO owner_id FROM users WHERE role = 'admin' ORDER BY created_at LIMIT 1;
            END IF;
            IF owner_id IS NULL THEN
                SELECT id INTO owner_id FROM users ORDER BY created_at LIMIT 1;
            END IF;

            IF owner_id IS NOT NULL THEN
                INSERT INTO vouchers
                    (admin_id, code, name, discount_type, discount_value,
                     min_order_value, max_uses, used_count,
                     valid_from, valid_to, status,
                     created_at, updated_at)
                SELECT
                    owner_id,
                    p.code,
                    p.code,
                    'percentage',
                    p.discount_percent,
                    COALESCE(p.min_booking_amount, 0),
                    COALESCE(p.max_uses, 100),
                    COALESCE(p.current_uses, 0),
                    p.created_at::date,
                    COALESCE(p.expires_at::date, DATE '2099-12-31'),
                    CASE WHEN p.is_active THEN 'active' ELSE 'disabled' END,
                    p.created_at,
                    p.updated_at
                FROM promo_codes p
                WHERE NOT EXISTS (SELECT 1 FROM vouchers v WHERE v.code = p.code);
            END IF;
        END $$;
        """
    )

    # --- 4. tour_bookings → tour_schedule + bookings + booking_item ----
    # 4a: aggregate tour_bookings into tour_schedule rows.
    op.execute(
        """
        INSERT INTO tour_schedule (tour_id, available_date, total_slots, booked_slots)
        SELECT
            tb.tour_id,
            tb.tour_date,
            GREATEST(
                COALESCE(t.max_participants, 20),
                SUM(CASE WHEN tb.status IN ('pending','confirmed','completed')
                         THEN COALESCE(tb.participants_count, 1) ELSE 0 END)::INTEGER
            ),
            SUM(CASE WHEN tb.status IN ('pending','confirmed')
                     THEN COALESCE(tb.participants_count, 1) ELSE 0 END)::INTEGER
        FROM tour_bookings tb
        JOIN tours t ON t.id = tb.tour_id
        GROUP BY tb.tour_id, tb.tour_date, t.max_participants
        ON CONFLICT (tour_id, available_date) DO NOTHING
        """
    )

    # 4b: one `bookings` row per tour_booking, reusing the tour_booking's id.
    # (tour_bookings.id is a fresh UUID; collisions with bookings.id are
    # astronomically improbable.)
    op.execute(
        """
        INSERT INTO bookings
            (id, user_id, total_price, status, special_requests,
             created_at, updated_at)
        SELECT
            tb.id,
            tb.user_id,
            tb.total_price,
            tb.status,
            tb.special_requests,
            tb.created_at,
            tb.updated_at
        FROM tour_bookings tb
        WHERE NOT EXISTS (SELECT 1 FROM bookings b WHERE b.id = tb.id)
        """
    )

    # 4c: matching booking_item rows (item_type='tour').
    op.execute(
        """
        INSERT INTO booking_item
            (booking_id, item_type, tour_schedule_id,
             unit_price, subtotal, quantity, status)
        SELECT
            tb.id,
            'tour',
            ts.id,
            CASE WHEN COALESCE(tb.participants_count, 0) > 0
                 THEN tb.total_price / tb.participants_count
                 ELSE tb.total_price
            END,
            tb.total_price,
            COALESCE(tb.participants_count, 1),
            tb.status
        FROM tour_bookings tb
        JOIN tour_schedule ts
            ON ts.tour_id = tb.tour_id
           AND ts.available_date = tb.tour_date
        WHERE NOT EXISTS (
            SELECT 1 FROM booking_item bi
            WHERE bi.booking_id = tb.id AND bi.item_type = 'tour'
        )
        """
    )

    # --- 5. Loyalty backfill -------------------------------------------
    op.execute(
        """
        INSERT INTO loyalty_transaction (user_id, points, type, description)
        SELECT u.id, u.loyalty_points, 'adjust',
               'legacy backfill from migration 006'
        FROM users u
        WHERE u.loyalty_points > 0
          AND NOT EXISTS (
              SELECT 1 FROM loyalty_transaction lt
              WHERE lt.user_id = u.id
                AND lt.description = 'legacy backfill from migration 006'
          )
        """
    )


def downgrade() -> None:
    # 5. Loyalty backfill
    op.execute(
        "DELETE FROM loyalty_transaction "
        "WHERE description = 'legacy backfill from migration 006'"
    )

    # 4. Remove tour-derived booking_item + bookings (ids come from tour_bookings).
    op.execute(
        "DELETE FROM booking_item "
        "WHERE item_type = 'tour' "
        "AND booking_id IN (SELECT id FROM tour_bookings)"
    )
    op.execute(
        "DELETE FROM voucher_usage "
        "WHERE booking_id IN (SELECT id FROM tour_bookings)"
    )
    op.execute("DELETE FROM bookings WHERE id IN (SELECT id FROM tour_bookings)")

    # Also remove any other non-room bookings created post-upgrade (best effort).
    op.execute(
        "DELETE FROM booking_item WHERE booking_id IN "
        "(SELECT id FROM bookings WHERE room_id IS NULL)"
    )
    op.execute("DELETE FROM bookings WHERE room_id IS NULL")

    # 3. Remove vouchers we created from promo_codes.
    op.execute(
        "DELETE FROM voucher_usage WHERE voucher_id IN "
        "(SELECT v.id FROM vouchers v JOIN promo_codes p ON p.code = v.code)"
    )
    op.execute(
        "DELETE FROM vouchers WHERE code IN (SELECT code FROM promo_codes)"
    )

    # 2. Room booking_items (safe because legacy bookings are still present).
    op.execute("DELETE FROM booking_item WHERE item_type = 'room'")

    # 1. Revert booking column changes.
    op.drop_index("ix_bookings_voucher_id", table_name="bookings")
    op.drop_constraint("fk_bookings_voucher_id", "bookings", type_="foreignkey")
    op.drop_column("bookings", "points_redeemed")
    op.drop_column("bookings", "points_earned")
    op.drop_column("bookings", "discount_amount")
    op.drop_column("bookings", "voucher_id")

    op.alter_column("bookings", "check_out", nullable=False)
    op.alter_column("bookings", "check_in", nullable=False)
    op.alter_column("bookings", "room_id", nullable=False)
