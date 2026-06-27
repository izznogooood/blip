import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.clients.radarr_client import RadarrClient
from app.core.database import get_session
from app.schemas.settings import MINIMUM_AVAILABILITY_OPTIONS
from app.services.movie_service import MOVIE_LISTS
from app.services.radarr_service import RadarrService
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


def get_settings_service(
    session: Session = Depends(get_session),
) -> SettingsService:
    return SettingsService(session)


def _radarr_options_context(
    base_url: str | None,
    api_key: str | None,
    *,
    current_root_folder: str | None,
    current_profile_id: int | None,
) -> dict[str, object]:
    """Fetch Radarr root folders / quality profiles for the dropdowns.

    Fails soft: if Radarr is unset or unreachable, returns an ``error`` so the
    template preserves the saved defaults (as hidden inputs) and the user can
    still save the rest of the settings.
    """
    context: dict[str, object] = {
        "root_folders": [],
        "profiles": [],
        "current_root_folder": current_root_folder,
        "current_profile_id": current_profile_id,
        "error": None,
    }
    if not base_url or not api_key:
        context["error"] = "Enter a Radarr URL and API key, then reload options."
        return context
    radarr = RadarrService(RadarrClient(base_url, api_key))
    try:
        context["root_folders"] = radarr.root_folders()
        context["profiles"] = radarr.quality_profiles()
    except httpx.HTTPError as exc:
        logger.warning("Radarr options lookup failed: %s", type(exc).__name__)
        context["error"] = "Could not reach Radarr with those settings."
    return context


@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    saved: bool = False,
    service: SettingsService = Depends(get_settings_service),
) -> HTMLResponse:
    row = service.get_row()
    resolved = service.resolve()
    options = _radarr_options_context(
        resolved.radarr_base_url,
        resolved.radarr_api_key,
        current_root_folder=resolved.radarr_default_root_folder,
        current_profile_id=resolved.radarr_default_quality_profile_id,
    )
    context: dict[str, object] = {
        "app_name": "Blip",
        "lists": MOVIE_LISTS,
        "row": row,
        "resolved": resolved,
        "minimum_availability_options": MINIMUM_AVAILABILITY_OPTIONS,
        "options": options,
        "saved": saved,
    }
    return templates.TemplateResponse(request, "settings.html", context)


@router.get("/settings/radarr-options", response_class=HTMLResponse)
def radarr_options(
    request: Request,
    radarr_base_url: str = "",
    radarr_api_key: str = "",
    service: SettingsService = Depends(get_settings_service),
) -> HTMLResponse:
    """HTMX endpoint: render the Radarr dropdowns for the given credentials.

    The form sends the live credential inputs; when they are blank we fall back
    to the resolved (DB → env) settings so the dropdowns also populate on first
    page load.
    """
    resolved = service.resolve()
    base_url = radarr_base_url.strip() or resolved.radarr_base_url
    api_key = radarr_api_key.strip() or resolved.radarr_api_key
    context = _radarr_options_context(
        base_url,
        api_key,
        current_root_folder=resolved.radarr_default_root_folder,
        current_profile_id=resolved.radarr_default_quality_profile_id,
    )
    return templates.TemplateResponse(
        request, "partials/settings_radarr_options.html", context
    )


@router.post("/settings")
def save_settings(
    service: SettingsService = Depends(get_settings_service),
    tmdb_api_key: str = Form(""),
    radarr_base_url: str = Form(""),
    radarr_api_key: str = Form(""),
    radarr_default_root_folder: str = Form(""),
    radarr_default_quality_profile_id: str = Form(""),
    radarr_default_minimum_availability: str = Form("released"),
) -> RedirectResponse:
    profile_id = radarr_default_quality_profile_id.strip()
    values: dict[str, object] = {
        "radarr_base_url": radarr_base_url,
        "radarr_default_root_folder": radarr_default_root_folder,
        "radarr_default_quality_profile_id": int(profile_id) if profile_id else None,
        "radarr_default_minimum_availability": radarr_default_minimum_availability,
    }
    # Secrets use the "leave blank to keep" pattern: an empty field means
    # "unchanged", so the stored key is never silently wiped on save and is
    # never echoed back into the form.
    if tmdb_api_key.strip():
        values["tmdb_api_key"] = tmdb_api_key
    if radarr_api_key.strip():
        values["radarr_api_key"] = radarr_api_key
    service.save(values)
    # PRG: redirect so a refresh doesn't re-submit the form.
    return RedirectResponse("/settings?saved=true", status_code=303)
