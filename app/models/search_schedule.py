from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Like the settings row, the schedule lives in a single row with a fixed key.
SCHEDULE_ROW_ID = 1


class SearchSchedule(Base):
    """State for the recurring Radarr "Search Missing Movies" job — one row (id=1).

    Kept in its own table rather than as columns on ``app_settings`` because the
    app has no migrations (``init_db`` only runs ``create_all``, which adds
    missing tables but never new columns to an existing one). A fresh table is
    created cleanly on existing databases.

    ``next_run_at`` / ``last_run_at`` are Unix epoch seconds (floats), matching
    the ``CachedResponse.expires_at`` convention.
    """

    __tablename__ = "search_schedule"

    id: Mapped[int] = mapped_column(primary_key=True, default=SCHEDULE_ROW_ID)

    # "off" | "daily" | "weekly"
    schedule: Mapped[str] = mapped_column(String, nullable=False, default="off")
    next_run_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_run_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Short human tag for the last run: "ok", "skipped", or a brief error label.
    last_result: Mapped[str | None] = mapped_column(String, nullable=True)
