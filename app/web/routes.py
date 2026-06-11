import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.clients.tmdb_client import TMDBClient
from app.core.config import settings
from app.services.movie_service import MovieService

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


def get_movie_service() -> MovieService | None:
    """Build a MovieService from configured settings, or None if unconfigured."""
    if not settings.tmdb_api_key:
        return None
    return MovieService(TMDBClient(settings.tmdb_api_key))


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {"app_name": "Blip"})


@router.get("/movies", response_class=HTMLResponse)
def movies(
    request: Request,
    list: str = "in_theaters",
    page: int = 1,
    service: MovieService | None = Depends(get_movie_service),
) -> HTMLResponse:
    """Return the movie grid partial for the given list (HTMX endpoint)."""
    context: dict[str, object] = {"movies": [], "error": None}

    if service is None:
        context["error"] = "TMDB API key is not configured."
        return templates.TemplateResponse(request, "partials/movie_grid.html", context)

    if list != "in_theaters":
        context["error"] = f"Unknown list: {list}."
        return templates.TemplateResponse(request, "partials/movie_grid.html", context)

    try:
        context["movies"] = service.in_theaters(page=page)
    except httpx.HTTPStatusError as exc:
        # Log status + path only — never the full URL, which carries the API key.
        logger.warning(
            "TMDB request failed: HTTP %s for %s (list=%s page=%s)",
            exc.response.status_code,
            exc.request.url.path,
            list,
            page,
        )
        if exc.response.status_code == 401:
            context["error"] = "TMDB API key is missing or invalid. Check your settings."
        else:
            context["error"] = "Could not load movies from TMDB right now."
    except httpx.HTTPError as exc:
        logger.warning(
            "TMDB request failed: %s (list=%s page=%s)",
            type(exc).__name__,
            list,
            page,
        )
        context["error"] = "Could not load movies from TMDB right now."

    return templates.TemplateResponse(request, "partials/movie_grid.html", context)


@router.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
