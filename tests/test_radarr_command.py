import json

import httpx

from app.clients.radarr_client import RadarrClient
from app.services.radarr_service import RadarrService


def test_command_posts_name_with_api_key_header() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["json"] = json.loads(request.content)
        captured["api_key"] = request.headers.get("X-Api-Key")
        return httpx.Response(201, json={"name": "MissingMoviesSearch", "status": "queued"})

    client = RadarrClient("http://radarr", "secret", transport=httpx.MockTransport(handler))
    result = client.command("MissingMoviesSearch")

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v3/command"
    assert captured["json"] == {"name": "MissingMoviesSearch"}
    assert captured["api_key"] == "secret"
    assert result["status"] == "queued"


def test_search_missing_triggers_the_named_command() -> None:
    class _Stub:
        def __init__(self) -> None:
            self.called: str | None = None
            self.kwargs: dict = {}

        def command(self, name: str, **kwargs: str) -> dict:
            self.called = name
            self.kwargs = kwargs
            return {"name": name}

    stub = _Stub()
    RadarrService(stub).search_missing()
    assert stub.called == "MissingMoviesSearch"
    assert stub.kwargs == {"filterKey": "status", "filterValue": "released"}
