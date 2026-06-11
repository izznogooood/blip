# Blip Implementation Plan

Build the app in small vertical slices.

Do not implement all features at once.

Each milestone should leave the app runnable.

## Progress

| Milestone | Status |
|---|---|
| 1. Project skeleton | ✅ Complete |
| 2. TMDB list rendering | ✅ Complete |
| 3. List tabs and Load More | ✅ Complete |
| 4. SQLite caching | ✅ Complete |
| 5. Radarr read integration | ✅ Complete |
| 6. Settings | ⬜ Not started |
| 7. Add and Add + Search | ⬜ Not started |
| 8. Synopsis modal and trailer | ⬜ Not started |
| 9. Polish and tests | ⬜ Not started |

## Milestone 1: Project skeleton — ✅ Complete

Goal: A runnable FastAPI app in Docker.

Tasks:

1. Create Python project using `pyproject.toml`.
2. Use Python 3.12+.
3. Add FastAPI, Uvicorn, Jinja2, SQLModel or SQLAlchemy, httpx, pytest.
4. Create basic app structure:
   - `app/main.py`
   - `app/core/config.py`
   - `app/core/database.py`
   - `app/web/routes.py`
   - `app/templates/base.html`
   - `app/templates/index.html`
5. Add Dockerfile.
6. Add docker-compose.yml.
7. Add `.env.example`.
8. Add basic health endpoint.
9. Add one basic HTML page at `/`.

Acceptance criteria:

- ✅ `docker compose up` starts the app. (`docker compose config` validated; image not built end-to-end.)
- ✅ Visiting `/` shows a Blip landing page.
- ✅ `/health` returns OK.
- ✅ `pytest` runs successfully. (2 passed)

Notes for later milestones:

- ORM is SQLAlchemy 2.x (ADR-006); `Base` + `init_db()` + `get_session()` live in `app/core/database.py`.
- Env-based config is in `app/core/config.py` (`Settings`); DB-stored settings will layer on top in Milestone 6.
- App is wired via a `create_app()` factory in `app/main.py`; `init_db()` runs in the FastAPI `lifespan` startup.

## Milestone 2: TMDB list rendering — ✅ Complete

Goal: Render one real TMDB movie list.

Tasks:

1. Add TMDB API key config.
2. Create `TMDBClient`.
3. Fetch "In Theaters" movies from TMDB.
4. Map TMDB responses into internal typed movie schema.
5. Render movie cards with:
   - poster
   - title
   - year
   - TMDB rating
6. Add basic HTMX route for switching/loading this list.

Acceptance criteria:

- ✅ `/` shows real movie cards from TMDB. (Grid loads via HTMX `GET /movies`; verified with a stubbed client. Live TMDB call requires `TMDB_API_KEY`.)
- ✅ Missing poster data does not break rendering. (Card shows a "No poster" placeholder; mapping tolerates missing title/year/rating.)
- ✅ Code has basic tests for TMDB mapping. (`tests/test_tmdb_mapping.py`, 8 tests; full suite 10 passed.)

Notes for later milestones:

- `TMDBClient` (`app/clients/tmdb_client.py`) is HTTP-only and returns raw JSON; it uses TMDB v3 (`api_key` query param) and `region="US"` for In Theaters. Currently exposes `now_playing()`.
- TMDB → internal mapping lives in `Movie.from_tmdb()` (`app/schemas/movie.py`); business orchestration in `MovieService` (`app/services/movie_service.py`).
- Route `GET /movies?list=<id>&page=<n>` returns the `partials/movie_grid.html` fragment for HTMX. Only `in_theaters` is wired; other list ids return a friendly error. The list-switching/tabs UI and Load More come in Milestone 3.
- Service is built via the `get_movie_service` FastAPI dependency, which returns `None` when `tmdb_api_key` is unset (grid then shows "not configured"). Override this dependency in tests to avoid network.

## Milestone 3: List tabs and Load More — ✅ Complete

Goal: Add all v1 lists and incremental loading.

Lists:

- In Theaters
- Upcoming Theatrical
- New at Home
- Upcoming at Home
- Top Rated

Tasks:

1. Add top tab navigation.
2. Implement HTMX list switching.
3. Implement Load More button.
4. Switching list resets to page 1.
5. Load More appends next page to existing cards.

Acceptance criteria:

- ✅ Each list tab works. (Five tabs from `MOVIE_LISTS`; four map to TMDB endpoints and "Top Rated" is an aggregate of the others — see ADR-008. Verified per-list dispatch and aggregation with stubs.)
- ✅ Load More appends movies. (Page 1 returns the full `#movie-cards` grid; page > 1 returns an append fragment whose cards swap `beforeend` into the grid and whose Load More button swaps itself out-of-band. Driven by TMDB `total_pages` via `MoviePage.has_more`.)
- ✅ Switching tabs resets list state. (Tab `hx-get` targets `#movie-list` with `innerHTML` and no page param → page 1, replacing all prior cards.)

Notes for later milestones:

- List registry is `MOVIE_LISTS` (id, label) in `app/services/movie_service.py`; `MovieService.movies(list_id, page)` dispatches and returns a `MoviePage` (`app/schemas/movie.py`). Unknown ids raise `UnknownListError`.
- TMDB endpoints per list resolved in ADR-008 (resolves PRD §25 #1/#2). At-home lists use `/discover/movie` with `with_release_type=4|5` and a `release_date` window computed from `date.today()`.
- Route `GET /movies?list=&page=` returns `partials/movie_grid.html` for page 1 (and all error cases) and `partials/movie_append.html` for page > 1. Card loop is shared via `partials/_cards.html`; the button lives in `partials/_load_more.html` (pass `oob=True` to swap it out-of-band).
- "Top Rated" is **not** a TMDB endpoint — `MovieService._top_rated()` aggregates page 1 of every other list (anything in `MOVIE_LISTS` except itself), dedupes by id, sorts by rating, and returns a single page (`total_pages=1`) so it has **no Load More**. A caption from `LIST_DESCRIPTIONS` explains the bounded scope. Adding a list to the registry auto-feeds Top Rated. See ADR-008.
- `LIST_DESCRIPTIONS` (`app/services/movie_service.py`) maps a list id → optional caption rendered above its grid; the route passes it as `caption`. Reusable for any future list needing an explainer.
- No caching yet — each list/page load hits TMDB live. Note Top Rated fans out to ~4 source calls per load, so it benefits most from Milestone 4 caching.

## Milestone 4: SQLite caching — ✅ Complete

Goal: Cache TMDB responses.

Tasks:

1. ✅ Add SQLite models for cached API responses. (`CachedResponse`, `app/models/cache.py`.)
2. ✅ Cache list responses for 1 hour. (`LIST_CACHE_TTL = 3600`.)
3. ✅ Cache movie details/trailers for 24 hours. (`DETAILS_CACHE_TTL = 86400` defined; wiring deferred to Milestone 8, where detail/trailer fetching is introduced.)
4. ✅ Add manual refresh action to bypass cache. (Per-list **Refresh** button → `?refresh=true` → `force_refresh`.)

Acceptance criteria:

- ✅ Repeated list loads use cache. (`MovieService` reads/writes via `CacheService`; verified by call-counting tests.)
- ✅ Manual refresh fetches fresh data. (`force_refresh=True` bypasses the read and rewrites the entry; propagated through Top Rated to its source lists.)
- ✅ Tests cover cache hit/miss behavior. (`tests/test_cache_service.py`: miss/round-trip/expiry/overwrite + service hit/miss/refresh/expiry/no-cache. Full suite passes.)

Notes for later milestones:

- `CacheService` (`app/services/cache_service.py`) is a generic TTL cache over the `cached_responses` table: `get(key)`, `set(key, value, ttl)`. `expires_at` is stored as a Unix epoch float (tz-free, avoids SQLite datetime quirks); the clock is injectable (`clock=`) for deterministic expiry tests. Expired entries are pruned on read.
- Caching is wired in `MovieService` via `_fetch_list` + `_cached`, keyed `tmdb:list:{list_id}:{page}`. The cache is **optional** (`MovieService(client, cache=None)` still works — every load hits the client), so existing tests that construct a bare service are unaffected.
- The route builds `CacheService` from the request-scoped `get_session` dependency inside `get_movie_service`. Tests that override `get_movie_service` bypass the DB entirely.
- `init_db()` now imports `app.models.cache` so the table is registered on `Base.metadata` before `create_all`. Add future models to the same import site (or an `app/models/__init__.py` aggregate) so they are created at startup.
- Only list payloads are cached today. Detail/trailer caching (Milestone 8) should reuse `CacheService` with `DETAILS_CACHE_TTL` and a `tmdb:detail:{id}` key.

## Milestone 5: Radarr read integration — ✅ Complete

Goal: Show Radarr status on cards.

Tasks:

1. ✅ Add Radarr config (base URL, API key). (Already on `Settings`; no change needed — env fallback per ADR-004.)
2. ✅ Create `RadarrClient`. (`app/clients/radarr_client.py`, HTTP-only, `X-Api-Key` header.)
3. ✅ Fetch Radarr movies. (`RadarrClient.movies()` → `/api/v3/movie`.)
4. ✅ Fetch quality profiles. (`/api/v3/qualityprofile` → `QualityProfile`.)
5. ✅ Fetch root folders. (`/api/v3/rootfolder` → `RootFolder`.)
6. ✅ Map Radarr movie data to internal status. (`status_from_radarr`, see ADR-010.)
7. ✅ Merge Radarr status into movie cards. (`RadarrService.annotate()` from the route, fail-soft on Radarr outage.)
8. ✅ Grey/desaturate cards already in Radarr. (`grayscale opacity-60` on existing posters + status badge.)

Acceptance criteria:

- ✅ Cards show Radarr status. (Colour-coded badge per status, PRD §20.)
- ✅ Existing Radarr movies are visually marked. (Desaturated poster + "Already in Radarr" indicator.)
- ✅ Add buttons are disabled/replaced for existing movies. (Add buttons don't exist until M7; existing movies render the static "Already in Radarr" indicator in the action area, so M7 only needs to render buttons in the `else` branch.)
- ✅ Tests cover Radarr status mapping. (`tests/test_radarr_status.py`: status precedence, id-map dedupe/skip, annotate, profile/folder mapping, route badge+grayscale, Radarr-unconfigured render. Full suite passes.)

Notes for later milestones:

- `RadarrClient` (`app/clients/radarr_client.py`) is HTTP-only and returns raw JSON lists; the API key goes in the `X-Api-Key` header (never a URL/log). Injectable `transport` for tests.
- `RadarrService` (`app/services/radarr_service.py`): `statuses_by_tmdb_id()` (one library call → `{tmdbId: RadarrStatus}`), `annotate(movies)` (mutates `Movie.radarr_status`), plus `quality_profiles()`/`root_folders()` ready for **M6 settings** and **M7 add**.
- Status precedence lives in `status_from_radarr` (`app/schemas/radarr.py`): file → Downloaded; else unmonitored → Unmonitored; else monitored → Missing; else Unknown. See ADR-010.
- `Movie` gained `radarr_status: RadarrStatus | None` and an `in_radarr` property. `None` = not in library = addable (the M7 Add buttons key off this).
- Route builds Radarr from `get_radarr_service` (returns `None` if base URL or key is unset → cards render with no status). Annotation is wrapped in `_annotate_radarr`, which logs and continues on `httpx.HTTPError` so a Radarr outage never breaks browsing.
- **No Radarr caching yet** — the library is fetched once per `/movies` request. If this proves heavy, wrap it with `CacheService` (a short TTL) like the TMDB lists; left out for now per KISS.
- **Env reminder:** `RADARR_BASE_URL` must be set for live status (LAN IP:7878, not `localhost`, since Blip runs in Docker).

## Milestone 6: Settings

Goal: Configure Radarr defaults through the app.

Tasks:

1. Add settings storage in SQLite.
2. Add settings page/modal.
3. Allow setting:
   - TMDB API key
   - Radarr base URL
   - Radarr API key
   - default root folder
   - default quality profile
   - default minimum availability
4. Fetch root folders and quality profiles from Radarr.
5. Provide env fallback when settings are missing.

Acceptance criteria:

- User can configure required settings in the UI.
- Radarr dropdowns are populated from live Radarr API.
- Env fallback works.

## Milestone 7: Add and Add + Search

Goal: Add movies to Radarr.

Tasks:

1. Implement Add action.
2. Implement Add + Search action.
3. Use configured root folder and quality profile.
4. Default minimum availability is `released`.
5. Allow quality profile override per movie if simple.
6. Show success/error feedback through HTMX.
7. Update card status after add.

Acceptance criteria:

- Add sends movie to Radarr.
- Add + Search sends movie and triggers search.
- Errors show visible messages.
- API keys are never exposed to browser.

## Milestone 8: Synopsis modal and trailer

Goal: Add detail polish.

Tasks:

1. Fetch movie overview/synopsis from TMDB.
2. Fetch TMDB videos/trailer.
3. Clicking poster opens modal.
4. Modal shows synopsis and trailer link.
5. Trailer opens YouTube in new tab.

Acceptance criteria:

- Poster click works on desktop/tablet/phone.
- Trailer button appears only when trailer exists.

## Milestone 9: Polish and tests

Goal: Make v1 feel complete.

Tasks:

1. Responsive card layout.
2. Clean empty/error/loading states.
3. Improve visual status badges.
4. Add pytest coverage for:
   - TMDB mapping
   - Radarr mapping
   - cache service
   - settings fallback
   - add/add+search service behavior
5. Update README.

Acceptance criteria:

- App is usable on desktop and tablet.
- Tests pass.
- README explains setup clearly.