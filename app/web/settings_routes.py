import logging
import time
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.clients.radarr_client import RadarrClient
from app.core.database import get_session
from app.schemas.settings import MINIMUM_AVAILABILITY_OPTIONS
from app.services.radarr_service import RadarrService
from app.services.search_schedule_service import (
    SCHEDULE_OPTIONS,
    SearchScheduleService,
)
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


def get_settings_service(
    session: Session = Depends(get_session),
) -> SettingsService:
    return SettingsService(session)


def get_schedule_service(
    session: Session = Depends(get_session),
) -> SearchScheduleService:
    return SearchScheduleService(session)


def _format_epoch(ts: float | None) -> str | None:
    """Format an epoch timestamp in the server's local time, or None."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


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


def _schedule_context(schedule_service: SearchScheduleService) -> dict[str, object]:
    row = schedule_service.get()
    return {
        "schedule_options": SCHEDULE_OPTIONS,
        "schedule_value": row.schedule,
        "schedule_last_run": _format_epoch(row.last_run_at),
        "schedule_next_run": _format_epoch(row.next_run_at),
        "schedule_last_result": row.last_result,
    }


@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    saved: bool = False,
    service: SettingsService = Depends(get_settings_service),
    schedule_service: SearchScheduleService = Depends(get_schedule_service),
) -> HTMLResponse:
    row = service.get_row()
    resolved = service.resolve()
    options = _radarr_options_context(
        resolved.radarr_base_url,
        resolved.radarr_api_key,
        current_root_folder=resolved.radarr_default_root_folder,
        current_profile_id=resolved.radarr_default_quality_profile_id,
    )
    # NOTE: Do NOT pass 'lists' or 'genres' to this template context.
    # base.html uses {% if lists %} / {% if genres %} to conditionally
    # render the mobile drawer tabs and genre controls. Passing them here
    # would render list tabs on the settings page, where #movie-list does
    # not exist — the Alpine fallback redirect would then kick in, creating
    # a confusing UX (see ADR-017).
    context: dict[str, object] = {
        "app_name": "Blip",
        "row": row,
        "resolved": resolved,
        "minimum_availability_options": MINIMUM_AVAILABILITY_OPTIONS,
        "options": options,
        "saved": saved,
        **_schedule_context(schedule_service),
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
    schedule_service: SearchScheduleService = Depends(get_schedule_service),
    tmdb_api_key: str = Form(""),
    radarr_base_url: str = Form(""),
    radarr_api_key: str = Form(""),
    radarr_default_root_folder: str = Form(""),
    radarr_default_quality_profile_id: str = Form(""),
    radarr_default_minimum_availability: str = Form("released"),
    radarr_search_schedule: str = Form("off"),
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
    schedule_service.set_schedule(radarr_search_schedule)
    # PRG: redirect so a refresh doesn't re-submit the form.
    return RedirectResponse("/settings?saved=true", status_code=303)


@router.post("/settings/run-search-now", response_class=HTMLResponse)
def run_search_now(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    schedule_service: SearchScheduleService = Depends(get_schedule_service),
) -> HTMLResponse:
    """Manually trigger Radarr's Search Missing Movies, independent of schedule.

    Fails soft (like the options lookup): reports an error into the status line
    rather than raising. Does not touch the scheduled ``next_run_at``.
    """
    resolved = service.resolve()
    if not resolved.radarr_configured:
        message = "Radarr is not configured — add a URL and API key first."
    else:
        try:
            RadarrService(
                RadarrClient(resolved.radarr_base_url, resolved.radarr_api_key)
            ).search_missing()
            schedule_service.record_manual_run(run_at=time.time(), result="ok")
            message = "Search Missing Movies triggered in Radarr."
        except httpx.HTTPError as exc:
            logger.warning("Manual Radarr search failed: %s", type(exc).__name__)
            schedule_service.record_manual_run(
                run_at=time.time(), result=f"error: {type(exc).__name__}"
            )
            message = "Could not reach Radarr — check the connection settings."
    return templates.TemplateResponse(
        request,
        "partials/settings_run_search_result.html",
        {"message": message},
    )
