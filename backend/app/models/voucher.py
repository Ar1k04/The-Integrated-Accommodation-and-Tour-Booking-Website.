import enum
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class VoucherDiscountType(str, enum.Enum):
    percentage = "percentage"
    fixed = "fixed"


class VoucherStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    disabled = "disabled"


class VoucherApplicableTo(str, enum.Enum):
    all = "all"
    hotel = "hotel"
    tour = "tour"
    flight = "flight"


class VoucherLiteAPISyncStatus(str, enum.Enum):
    not_synced = "not_synced"
    synced = "synced"
    failed = "failed"
    disabled = "disabled"


class Voucher(Base):
    __tablename__ = "vouchers"
    __table_args__ = (
        CheckConstraint(
            "discount_type IN ('percentage', 'fixed')",
            name="ck_vouchers_discount_type",
        ),
        CheckConstraint(
            "status IN ('active', 'expired', 'disabled')",
            name="ck_vouchers_status",
        ),
        CheckConstraint(
            "applicable_to IN ('all', 'hotel', 'tour', 'flight')",
            name="ck_vouchers_applicable_to",
        ),
        CheckConstraint(
            "liteapi_sync_status IN ('not_synced', 'synced', 'failed', 'disabled')",
            name="ck_vouchers_liteapi_sync_status",
        ),
    )

    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    discount_type: Mapped[str] = mapped_column(
        String(20), default=VoucherDiscountType.percentage.value, server_default="percentage", nullable=False
    )
    discount_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    maximum_discount_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), default="USD", server_default="USD", nullable=False
    )
    min_order_value: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0, server_default="0", nullable=False
    )
    budget: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    budget_used: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0, server_default="0", nullable=False
    )
    max_uses: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=VoucherStatus.active.value, server_default="active", nullable=False
    )
    guest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms_and_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_to: Mapped[str] = mapped_column(
        String(20),
        default=VoucherApplicableTo.all.value,
        server_default="all",
        nullable=False,
    )
    liteapi_voucher_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    liteapi_sync_status: Mapped[str] = mapped_column(
        String(20),
        default=VoucherLiteAPISyncStatus.not_synced.value,
        server_default="not_synced",
        nullable=False,
    )
    liteapi_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    liteapi_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    admin = relationship("User", back_populates="vouchers_owned", foreign_keys=[admin_id])
    guest = relationship("User", foreign_keys=[guest_id])
    bookings = relationship("Booking", back_populates="voucher", lazy="selectin")
    usages = relationship("VoucherUsage", back_populates="voucher", cascade="all, delete-orphan", lazy="selectin")
