import json

import httpx

from app.clients.radarr_client import RadarrClient
from app.services.radarr_service import RadarrService


# ---------------------------------------------------------------------------
# Client: search_movies
# ---------------------------------------------------------------------------

def test_search_movies_posts_ids() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["json"] = json.loads(request.content)
        captured["api_key"] = request.headers.get("X-Api-Key")
        return httpx.Response(201, json={"name": "MoviesSearch", "status": "queued"})

    client = RadarrClient("http://radarr", "secret", transport=httpx.MockTransport(handler))
    result = client.search_movies([42, 99])

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v3/command"
    assert captured["json"] == {"name": "MoviesSearch", "movieIds": [42, 99]}
    assert captured["api_key"] == "secret"
    assert result["status"] == "queued"


# ---------------------------------------------------------------------------
# Client: get_missing_available_movies
# ---------------------------------------------------------------------------

def test_get_missing_available_movies_filters() -> None:
    library = [
        {"id": 1, "monitored": True, "hasFile": False, "isAvailable": True},
        {"id": 2, "monitored": True, "hasFile": True, "isAvailable": True},
        {"id": 3, "monitored": True, "hasFile": False, "isAvailable": False},
        {"id": 4, "monitored": False, "hasFile": False, "isAvailable": True},
        {"id": 5, "monitored": True, "hasFile": False, "isAvailable": True},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=library)

    client = RadarrClient("http://radarr", "key", transport=httpx.MockTransport(handler))
    result = client.get_missing_available_movies()

    assert [m["id"] for m in result] == [1, 5]


def test_get_missing_available_movies_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": 1, "monitored": False, "hasFile": False, "isAvailable": False}])

    client = RadarrClient("http://radarr", "key", transport=httpx.MockTransport(handler))
    assert client.get_missing_available_movies() == []


# ---------------------------------------------------------------------------
# Client: command (no filter kwargs)
# ---------------------------------------------------------------------------

def test_command_posts_name_only() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(201, json={"name": "SomeCommand", "status": "queued"})

    client = RadarrClient("http://radarr", "key", transport=httpx.MockTransport(handler))
    client.command("SomeCommand")
    assert captured["json"] == {"name": "SomeCommand"}


# ---------------------------------------------------------------------------
# Service: search_missing — two-step flow
# ---------------------------------------------------------------------------

class _StubClient:
    """Captures calls instead of hitting a live Radarr."""

    def __init__(self, available_movies: list[dict]) -> None:
        self._available = available_movies
        self.search_calls: list[list[int]] = []

    def get_missing_available_movies(self) -> list[dict]:
        return self._available

    def search_movies(self, movie_ids: list[int]) -> dict:
        self.search_calls.append(movie_ids)
        return {"name": "MoviesSearch", "status": "queued"}


def test_search_missing_filters_by_availability() -> None:
    stub = _StubClient([
        {"id": 10, "monitored": True, "hasFile": False, "isAvailable": True},
        {"id": 20, "monitored": True, "hasFile": False, "isAvailable": True},
    ])
    RadarrService(stub).search_missing()
    assert stub.search_calls == [[10, 20]]


def test_search_missing_skips_unavailable_movies() -> None:
    stub = _StubClient([
        {"id": 10, "monitored": True, "hasFile": False, "isAvailable": True},
    ])
    RadarrService(stub).search_missing()
    assert stub.search_calls == [[10]]


def test_search_missing_handles_empty_result() -> None:
    stub = _StubClient([])
    result = RadarrService(stub).search_missing()
    assert result == {}
    assert stub.search_calls == []
