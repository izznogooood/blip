# Blip Implementation Plan

Build the app in small vertical slices.

Do not implement all features at once.

Each milestone should leave the app runnable.

## Progress

| Milestone | Status |
|---|---|
| 1. Project skeleton | ✅ Complete |
| 2. TMDB list rendering | ⬜ Not started |
| 3. List tabs and Load More | ⬜ Not started |
| 4. SQLite caching | ⬜ Not started |
| 5. Radarr read integration | ⬜ Not started |
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

## Milestone 2: TMDB list rendering

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

- `/` shows real movie cards from TMDB.
- Missing poster data does not break rendering.
- Code has basic tests for TMDB mapping.

## Milestone 3: List tabs and Load More

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

- Each list tab works.
- Load More appends movies.
- Switching tabs resets list state.

## Milestone 4: SQLite caching

Goal: Cache TMDB responses.

Tasks:

1. Add SQLite models for cached API responses.
2. Cache list responses for 1 hour.
3. Cache movie details/trailers for 24 hours.
4. Add manual refresh action to bypass cache.

Acceptance criteria:

- Repeated list loads use cache.
- Manual refresh fetches fresh data.
- Tests cover cache hit/miss behavior.

## Milestone 5: Radarr read integration

Goal: Show Radarr status on cards.

Tasks:

1. Add Radarr config:
   - base URL
   - API key
2. Create `RadarrClient`.
3. Fetch Radarr movies.
4. Fetch quality profiles.
5. Fetch root folders.
6. Map Radarr movie data to internal status:
   - Missing
   - Downloaded
   - Unmonitored
   - Unknown
7. Merge Radarr status into movie cards.
8. Grey/desaturate cards already in Radarr.

Acceptance criteria:

- Cards show Radarr status.
- Existing Radarr movies are visually marked.
- Add buttons are disabled/replaced for existing movies.
- Tests cover Radarr status mapping.

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