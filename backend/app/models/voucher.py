import enum
import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String
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
    min_order_value: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0, server_default="0", nullable=False
    )
    max_uses: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=VoucherStatus.active.value, server_default="active", nullable=False
    )

    admin = relationship("User", back_populates="vouchers_owned", foreign_keys=[admin_id])
    bookings = relationship("Booking", back_populates="voucher", lazy="selectin")
    usages = relationship("VoucherUsage", back_populates="voucher", cascade="all, delete-orphan", lazy="selectin")
