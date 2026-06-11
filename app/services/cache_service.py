import json
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models.cache import CachedResponse

# Cache TTLs in seconds, per the PRD §13: list results for 1 hour, movie
# details/trailers for 24 hours. (Details caching is wired in a later milestone.)
LIST_CACHE_TTL = 60 * 60
DETAILS_CACHE_TTL = 24 * 60 * 60


class CacheService:
    """SQLite-backed TTL cache for JSON-serialisable external API payloads.

    Entries past their ``expires_at`` are treated as a miss and pruned on read.
    The clock is injectable so expiry can be tested without sleeping.
    """

    def __init__(
        self, session: Session, *, clock: Callable[[], float] = time.time
    ) -> None:
        self._session = session
        self._clock = clock

    def get(self, key: str) -> dict | None:
        """Return the cached payload for ``key``, or ``None`` if missing/expired."""
        entry = self._session.get(CachedResponse, key)
        if entry is None:
            return None
        if entry.expires_at <= self._clock():
            self._session.delete(entry)
            self._session.commit()
            return None
        return json.loads(entry.value)

    def set(self, key: str, value: dict, ttl: int) -> None:
        """Store ``value`` under ``key``, expiring ``ttl`` seconds from now."""
        expires_at = self._clock() + ttl
        encoded = json.dumps(value)
        entry = self._session.get(CachedResponse, key)
        if entry is None:
            self._session.add(
                CachedResponse(key=key, value=encoded, expires_at=expires_at)
            )
        else:
            entry.value = encoded
            entry.expires_at = expires_at
        self._session.commit()
