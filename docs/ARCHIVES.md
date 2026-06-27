# Completed Milestones — Archive

Detail dump for completed milestones. Not read by default; reference only.

## Milestone 1: Project skeleton — ✅

Goal: Runnable FastAPI app in Docker.
Done: pyproject (Py 3.12+), app structure (`main.py`, `core/config.py`, `core/database.py`,
`web/routes.py`, `templates/`), Dockerfile, docker-compose.yml, `.env.example`,
`/health`, landing page at `/`. pytest: 2 passed.
Notes: SQLAlchemy 2.x (ADR-006); `Base`/`init_db()`/`get_session()` in `core/database.py`;
env config via `Settings`; `create_app()` factory, `init_db()` in lifespan startup.

## Milestone 2: TMDB list rendering — ✅

Goal: Render one real TMDB list (In Theaters).
Done: `TMDBClient` (HTTP-only, v3 `api_key` param, `region=US`), `Movie.from_tmdb()`
mapping, `MovieService`, movie cards (poster/title/year/rating) via HTMX `GET /movies`.
Missing poster → placeholder; mapping tolerates missing fields. 8 mapping tests; suite 10 passed.
Notes: service built via `get_movie_service` dependency (returns `None` if no TMDB key —
override in tests to avoid network). Route returns `partials/movie_grid.html` fragment.

## Milestone 3: List tabs and Load More — ✅

Goal: All five v1 lists + incremental loading.
Done: tab nav with HTMX switching (resets to page 1), Load More appends via
`beforeend` swap + OOB button swap, driven by `MoviePage.has_more`.
Notes: list registry `MOVIE_LISTS` in `movie_service.py`; unknown ids raise `UnknownListError`.
Endpoints per list in ADR-008; at-home lists use `/discover/movie` with
`with_release_type=4|5` + date windows. Top Rated = aggregate of page 1 of all other
lists, deduped, rating-sorted, single page, no Load More (ADR-008); caption via
`LIST_DESCRIPTIONS`. No caching yet — Top Rated fans out to ~4 TMDB calls.

## Milestone 4: SQLite caching — ✅

Goal: Cache TMDB responses.
Done: generic `cached_responses` table + `CacheService` (`get`/`set`, epoch-float expiry,
injectable clock, prune-on-read). Lists cached 1h (`LIST_CACHE_TTL`); detail TTL defined
(24h) but wired in M8. Per-list Refresh button → `?refresh=true` → `force_refresh`,
propagates through Top Rated. Cache hit/miss/expiry/refresh tests pass. (ADR-009)
Notes: cache optional on `MovieService` (`cache=None` = live calls); keys
`tmdb:list:{list_id}:{page}`; `init_db()` imports `app.models.cache` — add future models
to same import site.

## Milestone 5: Radarr read integration — ✅

Goal: Radarr status on cards.
Done: `RadarrClient` (HTTP-only, `X-Api-Key` header, injectable transport):
movies, quality profiles, root folders. `RadarrService.statuses_by_tmdb_id()` /
`annotate()`. Status precedence in `status_from_radarr`: file → Downloaded;
unmonitored → Unmonitored; monitored → Missing; else Unknown (ADR-010).
Existing movies: desaturated poster + colour-coded badge. Tests pass.
Notes: `Movie.radarr_status: RadarrStatus | None`, `in_radarr` property — `None` = addable.
Route fail-soft via `_annotate_radarr` (logs + continues on `httpx.HTTPError`).
`RADARR_BASE_URL` must be LAN IP, not localhost (Docker). Radarr caching later → ADR-014.

## Milestone 6: Settings — ✅

Goal: Configure Radarr/TMDB through the app.
Done: single typed row `app_settings` (ADR-011), `GET/POST /settings` page,
`SettingsService.resolve()` → `ResolvedSettings` (DB over env, empty falls through).
Radarr dropdowns populated live via HTMX `GET /settings/radarr-options`, fail-soft.
Suite 59 passed.
Notes: secrets are "leave blank to keep" — never rendered into HTML.
`ResolvedSettings.radarr_configured` is the single "is Radarr usable" check.
Route deps resolve through SettingsService, so UI-entered keys work without restart.
`python-multipart` added as runtime dep (form parsing).

## Milestone 7: Add and Add + Search — ✅

Goal: Add movies to Radarr.
Done: `RadarrService.add()` — lookup via `/api/v3/movie/lookup/tmdb`, POST augmented
body to `/api/v3/movie`; Add + Search sets `addOptions.searchForMovie=true` (ADR-012).
Defaults from `SettingsService.resolve()`; per-card quality-profile `<select>` override.
Success → card re-renders desaturated with badge; errors render inline, keys stay server-side.
Notes: `POST /movies/add` rebuilds `Movie` from hidden card fields; card `<article>` has
`id="movie-card-{id}"`, Add form swaps it `outerHTML`. `add()` returns resulting
`RadarrStatus` so no extra Radarr call. Action area keys off `movie.in_radarr`.

## Milestone 8: Synopsis modal and trailer — ✅

Goal: Detail modal with synopsis + trailer.
Done: `TMDBClient.movie_details()` (`append_to_response=videos`), `MovieDetail` schema,
poster click → HTMX `GET /movies/{id}/modal` into shared `#modal` mount; trailer button
opens YouTube in new tab, hidden when no trailer. 24h detail cache wired. Suite 72 passed.
(ADR-013)
Notes: Add available from modal via shared `partials/_movie_actions.html`; modal success
closes modal + OOB-updates the grid card (`HX-Retarget`); failure keeps modal open with
inline error. Radarr library now cached 10 min with UI-driven refresh (ADR-014).

## Milestone 10: Genre Dropdown — ✅

Goal: Add a genre dropdown alongside the existing list tabs so users can browse TMDB genres.

### Changes

- **`app/schemas/movie.py`** — Added `Genre` pydantic model
- **`app/clients/tmdb_client.py`** — Added `genres()` → `GET /genre/movie/list`
- **`app/services/movie_service.py`** — Added `genres()` (24h cache), `genre_movies()` with 180-day discover params, `_genre_params()` with optional `sort_by_rating`
- **`app/web/routes.py`** — `index()` fetches genres for template; `movies()` accepts `genre_id` and `sort_by_rating` query params; caption looked up server-side via `_genre_caption()`
- **`app/templates/partials/list_tabs.html`** — Genre dropdown and "By rating" checkbox in the tab bar; Alpine tracks `activeTab`, `activeGenre`, `sortByRating`; tab click resets all
- **`app/templates/partials/_load_more.html`** — Preserves `genre_id` and `sort_by_rating` in Load More URL
- **`app/templates/partials/movie_grid.html`** — Refresh button preserves genre/sort params

### Key decisions (ADR-016)

- Genres fetched live from TMDB, cached 24h.
- 180-day lookback window with `primary_release_date.desc` (default) or `vote_average.desc` (toggle).
- Not added to `MOVIE_LISTS` — separate browsing dimension, doesn't pollute Top Rated.
- Dropdown uses HTMX attributes (`hx-trigger="change[this.value != '']"`); sort checkbox uses `hx-include` paired with container-level `hx-trigger`.

### Tests added

- Genre model mapping (normal + missing name)
- Genre movie dispatch (discover, 180-day window, default sort, rating sort)
- Genre route (caption, Load More preserves genre_id)

### Post-milestone fix (commit `1fa924c`)

**Bug**: Desktop genre trigger `change from:#genre-select[this.value != '']` was syntactically invalid in HTMX v2.0.3 — the parser requires filters `[expr]` immediately after the event name, before modifiers. The `from:` value swallowed `#genre-select[this.value` and remaining tokens caused a silent parser error.

**Fix**: Moved `hx-get`, `hx-target`, `hx-swap`, `hx-trigger`, `hx-include` directly onto the `<select>` and `<input>` elements (matching mobile pattern). No `from:` modifier needed; `this` in filter refers to the element itself.

## Milestone 11: Responsive Top Navigation — ✅

Goal: Redesign top navigation for desktop, tablet, and phone viewports while preserving all existing functionality.

### Changes

- **`app/templates/base.html`** — Responsive header: desktop row (`hidden md:flex`) shows Blip / TMDB / Settings inline; mobile row (`flex md:hidden`) shows Blip + hamburger/X SVG toggle. Alpine `x-data` moved to `<body>` (`navOpen`, `activeTab`, `activeGenre`, `sortByRating`) with body scroll lock (`:class="navOpen ? 'overflow-hidden' : ''"`) and ESC key handler. Mobile drawer (fixed overlay, slide-down transition, backdrop, explicit close button) with all nav items: 5 tabs, genre select (`#genre-select-mobile`), rating checkbox (`#sort-checkbox-mobile`), TMDB attribution, Settings link. Tabs check `document.getElementById('movie-list')` — if absent (settings page), redirect to `/?list=X` instead of HTMX. Settings link shows active state via `window.location.pathname`.
- **`app/templates/partials/list_tabs.html`** — Removed `x-data` (inherits from `<body>`). Nav gets `hidden md:flex` (desktop-only).
- **`app/static/app.css`** — Added `[x-cloak] { display: none !important; }` for Alpine flicker prevention.
- **`app/web/settings_routes.py`** — Added `MOVIE_LISTS` to settings page template context so drawer tabs render on the settings page.

### Post-milestone fix (commit `230d6b7`)

**Bug**: `hx-trigger="load"` on `#movie-list` (`index.html`) does not fire reliably on initial page load. Root cause: timing issue between HTMX v2's deferred `load` trigger and Alpine's initialization on `<body>` — Alpine's startup triggers HTMX's `MutationObserver`, swallowing the queued `load` callback.

**Fix**: Replaced with Alpine `x-init="$nextTick(() => htmx.ajax('GET', '/movies?list=in_theaters', {target: '#movie-list', swap: 'innerHTML'}))"`. `$nextTick` defers the call until after Alpine finishes its DOM reconciliation.

