from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_renders_landing_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Blip" in response.text


def test_movie_list_has_x_init_for_initial_load() -> None:
    """#movie-list triggers an HTMX load via Alpine x-init, not hx-trigger=load.

    hx-trigger=\"load\" is unreliable when HTMX is loaded with defer alongside
    Alpine (ADRs 017-018). This test ensures the Alpine-driven fallback
    (x-init with htmx.ajax) is present and correct.
    """
    response = client.get("/")
    assert 'id="movie-list"' in response.text
    assert "$nextTick" in response.text
    assert "htmx.ajax" in response.text
    assert "hx-trigger=\"load\"" not in response.text


def test_movie_list_div_has_no_click_triggerable_hx_get() -> None:
    """#movie-list must not carry a bare hx-get.

    HTMX's default trigger for a <div> is `click`, so an hx-get on the grid
    container would re-fetch (and reset) the grid whenever a bubbled click —
    such as opening a movie modal — reaches it. The initial load is driven by
    x-init/htmx.ajax instead.
    """
    response = client.get("/")
    div = response.text.split('id="movie-list"', 1)[1].split(">", 1)[0]
    assert "hx-get" not in div
