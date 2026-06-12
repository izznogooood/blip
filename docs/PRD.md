### PRD — Blip

#### Product name

**Blip**

#### One-liner

Blip is a LAN-hosted movie discovery app that lets the user browse movie lists and add selected movies directly to Radarr from one clean interface.

---

### 1. Background

The user currently discovers movies manually by browsing Rotten Tomatoes, identifying interesting movies, switching to Radarr, searching for the movie, selecting settings, and adding it manually.

This workflow is repetitive and fragmented.

Blip replaces that workflow with a single local web app where the user can:

1. Browse movie discovery lists.
2. See whether each movie already exists in Radarr.
3. View basic movie information.
4. Add the movie to Radarr.
5. Optionally add and immediately trigger a Radarr search.

---

### 2. Goals

#### Primary goals

- Provide one place to browse and add movies to Radarr.
- Replace manual Rotten Tomatoes browsing for discovery.
- Keep the system simple, local, and Docker-friendly.
- Use modern, clean Python backend architecture.
- Use a simple but polished frontend without SPA complexity.
- Make the codebase educational and industry-standard, not “basement code.”

#### Learning goals

The project should demonstrate:

- FastAPI application structure.
- Modern Python `3.12+` typing.
- Pydantic v2 models.
- Typed service/client architecture.
- API integration patterns.
- SQLite persistence.
- SQLModel or SQLAlchemy 2.x usage.
- pytest tests for important business logic.
- HTMX-based server-driven UI.
- Minimal frontend reactivity with Alpine.js.
- Docker Compose deployment.

---

### 3. Non-goals / out of scope for v1

The following are explicitly out of scope for v1:

- User authentication.
- Mobile app.
- Multi-user support.
- Jellyfin integration.
- Automatic scheduled adding.
- Rotten Tomatoes scraping.
- Torrent/indexer direct integration.
- Subtitles integration.
- Request approval workflows.
- Bulk adding.
- Complex SPA frontend using React/Vue.
- Remembering ignored movies.
- Advanced recommendation engine.
- Platform-specific streaming filtering.
- Browser extension.
- Reverse proxy support as a first-class feature.

---

### 4. Target environment

Blip is intended to run as a Docker Compose service on the user’s LAN.

Radarr is reachable over LAN IP/hostname.

Example access pattern:

```text
http://server-ip:port
```

No authentication is required for v1.

---

### 5. Recommended technology stack

#### Backend

- Python `3.12+`
- FastAPI
- Pydantic v2
- httpx
- SQLModel or SQLAlchemy 2.x
- SQLite
- pytest

#### Frontend

- Server-rendered HTML templates.
- Jinja2 templates.
- HTMX for server-driven interactivity.
- Alpine.js for local UI state.
- Tailwind CSS for styling.

#### Deployment

- Docker
- Docker Compose

---

### 6. Architecture decision

Use a **backend-first server-rendered architecture**.

Blip should not use React or Vue in v1.

#### Rationale

The app does not require complex client-side state. The main interactions are:

- switch list
- load more
- open synopsis modal
- add movie
- add movie and search
- update card state after action

These are a strong fit for HTMX and Alpine.js.

#### Frontend responsibility split

| Concern | Technology |
|---|---|
| Render movie cards | FastAPI + Jinja2 |
| Switch lists | HTMX |
| Load more | HTMX |
| Add movie | HTMX |
| Add + Search | HTMX |
| Button loading states | HTMX / Alpine.js |
| Synopsis modal | Alpine.js |
| Styling | Tailwind CSS |

This keeps the project simple, avoids a JavaScript build pipeline, and keeps the backend as the center of gravity.

---

### 7. Core user flow

#### Main flow

1. User opens Blip on LAN.
2. User selects a movie list from tabs at the top.
3. Blip loads the first page of movies from TMDB.
4. Blip checks each movie against Radarr.
5. Movies are shown as cards.
6. Cards show:
   - poster
   - title
   - year
   - TMDB rating
   - Radarr status
   - trailer link
   - Add button
   - Add + Search button
7. User clicks poster to view synopsis modal.
8. User clicks Add or Add + Search.
9. Blip sends the movie to Radarr using configured root folder and quality profile.
10. Blip updates the movie card with the new Radarr status.

#### Done-state example

The user can open Blip on the LAN, choose “Upcoming Theatrical,” see movie cards and synopsis, know which movies are already in Radarr, click Add/Search, and Radarr receives the movie with the correct root folder and quality profile.

---

### 8. Movie lists

Blip v1 shall support the following lists:

1. **In Theaters**
2. **Upcoming Theatrical**
3. **New at Home**
4. **Upcoming at Home**
5. **Top Rated**

#### Source

TMDB shall be the only movie metadata/discovery source in v1.

#### Region

Use US/global release data for v1.

No Norway-specific localization is required.

#### Notes on “At Home”

For v1, “At Home” means a movie appears to be available for home viewing through streaming subscription or digital rent/buy sources.

Blip does not need to show which specific platform the movie is available on in v1.

Platform display/filtering can be added later.

---

### 9. Sorting and pagination

#### Sorting

All movie lists should default to sorting by release date where applicable.

The implementation should be structured so additional filters/sorts can be added later.

#### Load more

Each list shall initially load one page of results.

At the bottom of the list, show a **Load More** button.

Clicking **Load More** appends the next page of results below the current cards.

When switching to another list, the current list state resets.

When switching back to a previous list, it loads fresh from page 1.

---

### 10. Movie card requirements

Each movie card shall display:

- Poster
- Title
- Year
- TMDB rating
- Radarr status badge
- Add button
- Add + Search button
- Trailer button/link, if trailer data is available

#### Synopsis

Clicking/tapping the poster opens a modal showing:

- poster/title
- synopsis/overview
- release date
- TMDB rating
- trailer link if available

This should work on desktop, tablet, and phone.

#### Trailer

If TMDB provides a YouTube trailer key, show a trailer button that opens YouTube in a new tab.

Format:

```text
https://www.youtube.com/watch?v={youtube_key}
```

If no trailer is found, hide the trailer button.

---

### 11. Radarr integration

#### Required Radarr capabilities

Blip must integrate with Radarr to:

1. Fetch existing movies.
2. Fetch quality profiles.
3. Fetch root folders.
4. Add a movie by TMDB ID.
5. Optionally trigger search when adding.
6. Display Radarr status on movie cards.

#### Configuration

Blip should support both:

1. Radarr configuration through app settings.
2. Fallback to environment variables.

Required Radarr config:

- Radarr base URL
- Radarr API key
- default root folder
- default quality profile
- default minimum availability

#### Minimum availability

Default value:

```text
released
```

Same default applies to all lists in v1.

#### Add behavior

Blip shall support two actions per movie:

1. **Add**
   - Adds movie to Radarr.
   - Does not immediately search.

2. **Add + Search**
   - Adds movie to Radarr.
   - Immediately tells Radarr to search for the movie.

#### Per-movie override

Blip should allow the default quality profile to be overridden per movie when adding.

This is useful for older movies where a lower quality profile may be acceptable.

Root folder does not need frequent per-movie override but may be available if simple.

#### Existing Radarr movie status

If a movie already exists in Radarr, the card shall show its actual Radarr status.

Known statuses should include:

- `Missing`
- `Downloaded`
- `Unmonitored`
- `Unknown`

Cards for movies already in Radarr should be visually greyed out/desaturated.

The user should still be able to inspect the movie card.

Add buttons should be disabled or replaced with a clear “Already in Radarr” state.

---

### 12. Settings

Blip shall provide a simple settings page/modal.

#### Settings fields

- TMDB API key
- Radarr base URL
- Radarr API key
- Default root folder
- Default quality profile
- Default minimum availability
- Cache TTL settings, if exposed

#### Radarr discovery

If Radarr URL/API key is valid, Blip should fetch:

- root folders
- quality profiles

The user can then select defaults from dropdowns.

#### Fallback

If settings are not configured in the database, Blip should read from environment variables.

Environment variables should be suitable for Docker Compose deployment.

---

### 13. Caching

Blip shall use SQLite-backed caching for TMDB responses.

#### Recommended cache behavior

- List results: cache for 1 hour.
- Movie details/trailers: cache for 24 hours.
- Manual refresh button per list.

#### Rationale

Caching improves perceived performance and reduces dependence on TMDB availability/rate limits.

#### Manual refresh

Each list should have a manual refresh action that bypasses or invalidates the cached list result.

---

### 14. Persistence

Use SQLite for local persistence.

#### Data that should be stored

- App settings
- Cached TMDB responses
- Optional Radarr status snapshot
- Add history / audit log

#### Data not stored in v1

- Ignored movies
- User accounts
- Personal ratings
- Watch history

---

### 15. Error handling

#### Add failures

If Add or Add + Search fails:

- Show a visible toast or inline error message.
- Do not crash the page.
- Preserve the card state.
- Log the detailed backend error server-side.

#### API failures

If TMDB fails:

- Show user-friendly error message.
- If cached data exists, optionally show stale cached data with a warning.

If Radarr fails:

- Show user-friendly error message.
- Existing movie statuses may show as `Unknown`.

#### Settings validation

Settings page should validate:

- TMDB API key works.
- Radarr URL/API key works.
- root folder is selected.
- quality profile is selected.

---

### 16. Security assumptions

Blip v1 runs on a trusted LAN.

No authentication is required.

However:

- API keys must never be exposed in browser-rendered HTML.
- Radarr API key must only be used server-side.
- TMDB API key should be server-side.
- Settings containing secrets should not be logged.
- Docker environment variables should not be printed at startup.

---

### 17. Suggested project structure

```text
blip/
  app/
    __init__.py
    main.py

    core/
      __init__.py
      config.py
      database.py
      logging.py

    models/
      __init__.py
      settings.py
      cache.py
      history.py

    schemas/
      __init__.py
      movie.py
      radarr.py
      settings.py

    services/
      __init__.py
      movie_service.py
      radarr_service.py
      settings_service.py
      cache_service.py

    clients/
      __init__.py
      tmdb_client.py
      radarr_client.py

    web/
      __init__.py
      routes.py
      settings_routes.py
      movie_routes.py

    templates/
      base.html
      index.html
      settings.html
      partials/
        movie_grid.html
        movie_card.html
        movie_modal.html
        list_tabs.html
        toast.html

    static/
      app.css
      app.js

  tests/
    test_movie_service.py
    test_radarr_service.py
    test_tmdb_client.py
    test_cache_service.py

  Dockerfile
  docker-compose.yml
  pyproject.toml
  README.md
  .env.example
```

---

### 18. Suggested backend layering

#### Clients

Clients handle external HTTP only.

Examples:

- `TMDBClient`
- `RadarrClient`

They should not contain business logic.

#### Services

Services contain app-specific business logic.

Examples:

- merge TMDB movie results with Radarr status
- decide whether Add buttons should be disabled
- resolve configured quality profile
- use cache before calling TMDB

#### Web routes

Routes should be thin.

They should:

- validate input
- call service methods
- return HTML templates or redirects/fragments

---

### 19. API integration assumptions

#### TMDB

Blip v1 uses TMDB for:

- movie discovery lists
- movie details
- posters
- release dates
- TMDB ratings
- trailers

#### Radarr

Blip v1 uses Radarr API for:

- current movie library
- quality profiles
- root folders
- movie add
- add and search

Implementation should verify exact Radarr endpoint payloads against the current Radarr API docs or live Radarr instance before coding.

---

### 20. UI requirements

#### General UI

The UI should be:

- clean
- responsive
- card-based
- usable on desktop, tablet, and phone
- optimized for quick browsing

#### Main page layout

Top area:

- app name/logo: `Blip`
- list tabs
- settings button

Main area:

- movie card grid

Bottom:

- Load More button

#### Card states

Cards should visually distinguish:

- not in Radarr
- missing in Radarr
- downloaded in Radarr
- unmonitored in Radarr
- unknown status

Suggested styling:

- Normal card: full color
- Existing in Radarr: desaturated poster
- Downloaded: green badge
- Missing: yellow/orange badge
- Unmonitored: grey badge
- Unknown: neutral badge

---

### 21. Testing requirements

v1 should include basic pytest coverage.

#### Required test areas

- TMDB response mapping to internal movie schema.
- Radarr movie status mapping.
- Cache hit/miss behavior.
- Add movie service behavior.
- Add + Search flag behavior.
- Settings fallback from env when database setting is missing.

No browser automation tests are required for v1.

---

### 22. Docker requirements

Blip must be runnable with:

```bash
docker compose up -d
```

#### Required files

- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `README.md`

#### Example environment variables

```env
BLIP_HOST=0.0.0.0
BLIP_PORT=8080

DATABASE_URL=sqlite:///./data/blip.db

TMDB_API_KEY=your_tmdb_api_key

RADARR_BASE_URL=http://192.168.1.50:7878
RADARR_API_KEY=your_radarr_api_key

RADARR_DEFAULT_ROOT_FOLDER=/movies
RADARR_DEFAULT_QUALITY_PROFILE_ID=1
RADARR_DEFAULT_MINIMUM_AVAILABILITY=released
```

SQLite database should be stored in a mounted Docker volume.

---

### 23. Milestones

#### Milestone 1 — Project skeleton

- FastAPI app starts.
- Docker Compose works.
- SQLite connection works.
- Base template renders.
- Basic Tailwind/HTMX/Alpine setup works.

#### Milestone 2 — TMDB discovery

- TMDB client works.
- In Theaters list renders.
- Upcoming Theatrical list renders.
- Movie cards render with poster/title/year/rating.
- Load More appends cards.

#### Milestone 3 — Radarr read integration

- Radarr settings can be configured.
- Root folders can be fetched.
- Quality profiles can be fetched.
- Existing Radarr movies are fetched.
- Cards show Radarr status.

#### Milestone 4 — Radarr add integration

- Add sends movie to Radarr.
- Add + Search sends movie to Radarr and triggers search.
- Card updates after add.
- Error handling works.

#### Milestone 5 — Settings and cache

- Settings page works.
- Env fallback works.
- TMDB responses are cached.
- Manual refresh bypasses cache.

#### Milestone 6 — Polish and tests

- Synopsis modal works.
- Trailer link works.
- Responsive UI polish.
- pytest coverage for core services.
- README completed.

---

### 24. Acceptance criteria

Blip v1 is complete when:

- The app runs through Docker Compose.
- The user can access it from the LAN.
- The user can configure TMDB and Radarr.
- The app can fetch Radarr quality profiles and root folders.
- The user can choose default root folder and quality profile.
- The app shows movie cards for:
  - In Theaters
  - Upcoming Theatrical
  - New at Home
  - Upcoming at Home
  - Top Rated
- Movie cards show poster, title, year, TMDB rating, and Radarr status.
- Clicking a poster opens a synopsis modal.
- Trailer button opens YouTube in a new tab when available.
- Load More appends additional movies.
- Switching lists resets the loaded page state.
- Movies already in Radarr are visually greyed out and status-labeled.
- Add adds the movie to Radarr.
- Add + Search adds the movie and triggers search.
- Add failures show a visible error without crashing.
- TMDB responses are cached.
- Manual refresh works.
- Basic pytest tests pass.

---

### 25. Open implementation questions for Claude Code

These should be resolved during implementation:

1. ~~Exact TMDB endpoints to use for “New at Home” and “Upcoming at Home.”~~ **Resolved: `/discover/movie` with `with_release_type=4|5` and a `release_date` window (see ADR-008).**
2. ~~Whether TMDB watch provider data is sufficient for at-home classification.~~ **Resolved: not used in v1; at-home is approximated via digital/physical release type (see ADR-008).**
3. ~~Exact current Radarr API payload for adding a movie by TMDB ID.~~ **Resolved: look up the movie via `/api/v3/movie/lookup/tmdb` and POST the augmented body to `/api/v3/movie` (see ADR-012).**
4. ~~Best way to trigger search immediately after add in the current Radarr API.~~ **Resolved: set `addOptions.searchForMovie=true` in the add call (see ADR-012).**
5. ~~Whether SQLModel or SQLAlchemy 2.x should be used.~~ **Resolved: SQLAlchemy 2.x (see ADR-006).**
6. ~~Whether settings should be stored as key-value rows or a single settings row.~~ **Resolved: a single typed settings row with environment-variable fallback (see ADR-011).**
7. ~~Whether Tailwind should stay CDN-only for v1 or later move to a build step.~~ **Resolved: CDN only for v1 (see ADR-007).**

