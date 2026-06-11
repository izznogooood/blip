from enum import Enum

from pydantic import BaseModel


class RadarrStatus(str, Enum):
    """A movie's status within the Radarr library, as shown on a card.

    ``str`` mixin so the value renders directly in templates and serialises
    cleanly. These are the only statuses Blip distinguishes in v1 (PRD §11).
    """

    DOWNLOADED = "Downloaded"
    MISSING = "Missing"
    UNMONITORED = "Unmonitored"
    UNKNOWN = "Unknown"


def status_from_radarr(movie: dict) -> RadarrStatus:
    """Map a single Radarr library movie payload to a :class:`RadarrStatus`.

    Order matters: a movie with a file is ``Downloaded`` regardless of its
    monitored flag; an unmonitored movie without a file is ``Unmonitored``; a
    monitored movie without a file is ``Missing``. Anything ambiguous (e.g. the
    expected fields are absent) falls back to ``Unknown``.
    """
    has_file = movie.get("hasFile")
    monitored = movie.get("monitored")

    if has_file:
        return RadarrStatus.DOWNLOADED
    if monitored is False:
        return RadarrStatus.UNMONITORED
    if monitored is True:
        return RadarrStatus.MISSING
    return RadarrStatus.UNKNOWN


class QualityProfile(BaseModel):
    """A Radarr quality profile (used for the settings/add milestones)."""

    id: int
    name: str

    @classmethod
    def from_radarr(cls, data: dict) -> "QualityProfile":
        return cls(id=data["id"], name=data.get("name") or f"Profile {data['id']}")


class RootFolder(BaseModel):
    """A Radarr root folder (used for the settings/add milestones)."""

    id: int
    path: str

    @classmethod
    def from_radarr(cls, data: dict) -> "RootFolder":
        return cls(id=data["id"], path=data.get("path") or "")
