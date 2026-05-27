from sqlalchemy import CHAR, Computed, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class City(Base):
    __tablename__ = "cities"
    __table_args__ = (UniqueConstraint("liteapi_id", name="uq_cities_liteapi_id"),)

    liteapi_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str] = mapped_column(
        CHAR(2), ForeignKey("countries.code", ondelete="CASCADE"), nullable=False, index=True
    )
    state: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    hotel_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    name_norm: Mapped[str] = mapped_column(
        Text, Computed("f_unaccent(name)", persisted=True), nullable=False
    )
    search_text: Mapped[str] = mapped_column(
        Text,
        Computed("f_unaccent(name) || ' ' || COALESCE(f_unaccent(state), '')", persisted=True),
        nullable=False,
    )
