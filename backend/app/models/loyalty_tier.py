from sqlalchemy import Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LoyaltyTier(Base):
    __tablename__ = "loyalty_tier"
    __table_args__ = (UniqueConstraint("name", name="uq_loyalty_tier_name"),)

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    min_points: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    max_points: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    benefits: Mapped[str | None] = mapped_column(Text)
    discount_percent: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0, server_default="0", nullable=False
    )

    users = relationship("User", back_populates="loyalty_tier", lazy="selectin")
