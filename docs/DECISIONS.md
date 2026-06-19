# Architecture Decisions

## ADR-001: Backend-first architecture

Blip uses a backend-first server-rendered architecture.

FastAPI renders HTML with Jinja2 templates. HTMX handles server-driven interactivity. Alpine.js handles small local UI state such as modals. Tailwind CSS handles styling.

Blip does not use React, Vue, Svelte, Next.js, Nuxt, Vite, or a JavaScript build pipeline in v1.

## ADR-002: Python backend

Use Python 3.12+ with modern typing syntax.

Prefer:

- `str | None` instead of `Optional[str]`
- `list[str]` instead of `List[str]`
- Pydantic v2 models
- typed service/client boundaries
- explicit return types

## ADR-003: Integration boundaries

External API clients handle HTTP and response parsing only.

Business logic lives in services.

Routes stay thin.

## ADR-004: Docker-first deployment

The app must run with Docker Compose.

SQLite data should live in a mounted Docker volume.

## ADR-005: KISS principle

Do not introduce unnecessary abstractions, background workers, queues, frontend frameworks, auth systems, or plugin architectures in v1.

## ADR-006: ORM choice — SQLAlchemy 2.x

Use SQLAlchemy 2.x with typed sessions and explicit models.

Rationale: it is the more standard and explicit option, and it fits the small model set in v1.

## ADR-007: Tailwind delivery — CDN only for v1

Use the Tailwind CSS CDN script.

Do not introduce an npm/Vite build step for CSS in v1.

## ADR-008: TMDB endpoints per movie list

Map the five v1 lists to TMDB endpoints as follows:

| List | Source | Notes |
|---|---|---|
| In Theaters | `/movie/now_playing` | region `US` |
| Upcoming Theatrical | `/movie/upcoming` | region `US` |
| New at Home | `/discover/movie` | `with_release_type=4\|5`, `release_date.gte=today-90d`, `release_date.lte=today`, `sort_by=primary_release_date.desc` |
| Upcoming at Home | `/discover/movie` | `with_release_type=4\|5`, `release_date.gte=today`, `release_date.lte=today+180d`, `sort_by=primary_release_date.asc` |
| Top Rated | aggregate of all other lists | page 1 of every other list, deduped by id, sorted by TMDB rating desc; single curated page, no Load More |

“At home” is approximated using digital or physical release type and a date window.

Top Rated is computed from the list registry rather than TMDB’s global top rated chart.

## ADR-009: TMDB response caching — generic key-value table, epoch TTL

Cache TMDB responses in a single generic `cached_responses` table with:

- `key`
- `value`
- `expires_at`

Use a `CacheService` with `get` and `set`.

Decisions:

- One generic table, not per-endpoint tables.
- Expiry is stored as a Unix epoch float.
- The clock is injectable for deterministic tests.
- Cache is optional on `MovieService`.
- Manual refresh bypasses the cache with `force_refresh`.
- Expired rows are pruned on read.

## ADR-010: Radarr read integration — status mapping and merge

Read Radarr state through a `RadarrClient` and `RadarrService`.

Decisions:

- Auth uses the `X-Api-Key` header.
- Status precedence is:
  - `hasFile` → `Downloaded`
  - else `monitored == false` → `Unmonitored`
  - else `monitored == true` → `Missing`
  - else `Unknown`
- Match on `tmdbId`.
- Merge Radarr data in the route and fail soft on HTTP errors.
- Radarr service is optional when unset.
- No Radarr caching in v1 unless later needed.

## ADR-011: Settings storage — single typed row, env fallback

Store app settings in a single-row `app_settings` table with typed columns.

Decisions:

- Single typed row, not key-value rows.
- Database values override environment values.
- Empty values fall through to env.
- Secret fields use “leave blank to keep”.
- Radarr dropdowns are fetched live and fail soft.
- `python-multipart` is required for settings forms.

## ADR-012: Radarr add — lookup-then-post, search via addOptions

Add movies through `RadarrService.add()`.

Decisions:

- Look up the movie via `/api/v3/movie/lookup/tmdb`.
- POST the augmented movie body back to `/api/v3/movie`.
- Use `addOptions.searchForMovie=true` for Add + Search.
- Root folder, quality profile, and minimum availability come from resolved settings.
- Quality profile can be overridden per movie.
- `add()` returns the resulting Radarr status.
- Add runs server-side only and fails soft.

## ADR-013: Synopsis modal — HTMX-loaded partial, append_to_response videos

Show movie details in a modal loaded on demand.

Decisions:

- Poster click loads `/movies/{id}/modal` into a shared mount.
- Use `append_to_response=videos` for details and trailer data.
- Trailer selection prefers official YouTube Trailer, then Trailer, then Teaser.
- Detail data is cached for 24 hours.
- Modal state is handled with Alpine.
- Add controls are shared between card and modal.
- Modal add success closes the modal and OOB-updates the card.
- Modal add failure keeps the modal open with inline error.

## ADR-014: Radarr library caching — 10 minute TTL with UI-driven refresh

Cache Radarr library-derived statuses for 10 minutes.

Decisions:

- Cache the status map, not raw Radarr payloads.
- Use a dedicated `RADARR_CACHE_TTL`.
- `annotate()` supports `force_refresh`.
- Refresh on explicit user intent and on initial list loads.
- Keep fail-soft behavior unchanged.

## ADR-015: Documentation structure — short current-state files, archive for history

Keep active docs short and use an archive for completed detail.

Decisions:

- `IMPLEMENTATION_PLAN.md` contains only:
  - progress table
  - short handoff notes
  - current state
  - a brief template for the next milestone
- `ARCHIVE.md` contains the detailed writeup of completed milestones.
- `DECISIONS.md` contains only lasting architectural decisions.
- Completed milestone notes should be moved out of the implementation plan.
- The implementation plan should not accumulate history over time.
- Keep docs optimized for low-token re-reading in future sessions.

## ADR-016: Genre discovery — live genre list, 180-day discover window, tabs-and-dropdown coexistence

Add a genre dropdown alongside the existing list tabs.

Decisions:
- Genres are fetched live from TMDB (`/genre/movie/list`) on page load and cached 24h.
- Genre discovery uses `/discover/movie` with `with_genres=<id>`, a 180-day lookback window, and `sort_by=primary_release_date.desc`.
- Genres are not added to `MOVIE_LISTS` — they are a separate browsing dimension and do not pollute the Top Rated aggregation.
- The dropdown uses Alpine.js for local state (active tab vs active genre) and HTMX for server requests via `htmx.ajax()`.
- Genre name is looked up server-side from the cached genre list for the grid caption.
- Load More preserves the `genre_id` query parameter.
