from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CachedResponse(Base):
    """A cached external API response.

    Keyed by an opaque request key (e.g. ``tmdb:list:in_theaters:1``). The
    payload is stored as a JSON string and ``expires_at`` is a Unix epoch in
    seconds — a timezone-free integer comparison that sidesteps SQLite's
    datetime serialisation quirks.
    """

    __tablename__ = "cached_responses"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[float] = mapped_column(Float)
