# Architecture Decisions

## ADR-001: Backend-first architecture

Blip uses a backend-first server-rendered architecture.

FastAPI renders HTML using Jinja2 templates. HTMX handles server-driven interactivity. Alpine.js handles small local UI state such as modals. Tailwind CSS handles styling.

Blip should not use React, Vue, Svelte, Next.js, Nuxt, Vite, or a JavaScript build pipeline in v1.

## ADR-002: Python backend

Use Python 3.12+ with modern typing syntax.

Prefer:

- `str | None` instead of `Optional[str]`
- `list[str]` instead of `List[str]`
- Pydantic v2 models
- typed service/client boundaries
- explicit return types

## ADR-003: Integration boundaries

External API clients should only handle HTTP and response parsing.

Business logic should live in services.

Routes should be thin.

## ADR-004: Docker-first deployment

The app must run with Docker Compose.

SQLite data should live in a mounted Docker volume.

## ADR-005: KISS principle

Do not introduce unnecessary abstractions, background workers, queues, frontend frameworks, auth systems, or plugin architectures in v1.

## ADR-006: ORM choice — SQLAlchemy 2.x

Use SQLAlchemy 2.x (with `DeclarativeBase` and typed `Session`) rather than SQLModel.

Rationale: SQLAlchemy 2.x is the more standard and explicit option, aligns with ADR-002's preference for explicit, typed boundaries, and has a larger and more mature ecosystem. SQLModel's main benefit (less boilerplate) is marginal given the small number of models in v1.

Resolves PRD §25 open question 5.

## ADR-007: Tailwind delivery — CDN only for v1

Use the Tailwind CSS CDN script. Do not introduce an npm/Vite build step for CSS in v1.

Rationale: keeps the project free of a JavaScript build pipeline (ADR-001) and matches the KISS principle. A build step can be revisited post-v1 if bundle size or purging becomes a concern.

Resolves PRD §25 open question 7.

## ADR-008: TMDB endpoints per movie list

Map the five v1 lists to TMDB endpoints as follows:

| List | Source | Notes |
|---|---|---|
| In Theaters | `/movie/now_playing` | region `US` |
| Upcoming Theatrical | `/movie/upcoming` | region `US` |
| New at Home | `/discover/movie` | `with_release_type=4\|5`, `release_date.gte=today-90d`, `release_date.lte=today`, `sort_by=primary_release_date.desc` |
| Upcoming at Home | `/discover/movie` | `with_release_type=4\|5`, `release_date.gte=today`, `release_date.lte=today+180d`, `sort_by=primary_release_date.asc` |
| Top Rated | aggregate of all other lists | page 1 of every other list, deduped by id, sorted by TMDB rating desc; single curated page, no Load More |

"At home" availability is approximated as a digital (release type 4) or physical (5) release within the date window, paired with `region`. This avoids a separate watch-provider lookup per movie in v1.

**Top Rated** is deliberately *not* TMDB's all-time `/movie/top_rated` chart. Blip's "Top Rated" means "the best-rated of the movies Blip is currently surfacing", so it is computed by unioning page 1 of every other entry in `MOVIE_LISTS` (anything except `top_rated` itself), deduping by movie id, and sorting by rating. This is driven entirely by the registry, so any list added in the future is automatically included with no extra wiring. Because the pool is bounded (page 1 of each source), Top Rated is presented as a single curated page with **no Load More**, and a short caption (`LIST_DESCRIPTIONS`) explains the scope so the bounded set is not mistaken for a truncated infinite feed.

Rationale: the theatrical lists have first-class TMDB endpoints. For "at home" there is no dedicated endpoint, so `/discover/movie` with release-type filtering is the standard approach and is sufficient for discovery; per-platform watch-provider data is explicitly out of scope for v1 (PRD §8). Date windows keep the lists relevant without storing state. The aggregate Top Rated keeps a single source of truth (the list registry) and stays correct as lists are added.

Resolves PRD §25 open questions 1 and 2.

## ADR-009: TMDB response caching — generic key-value table, epoch TTL

Cache TMDB responses in a single generic `cached_responses` table (`key` text PK, `value` JSON text, `expires_at` Unix epoch float) accessed through a `CacheService` (`get`/`set`), rather than per-list typed tables.

Decisions:

- **One generic table, not per-endpoint tables.** A single `(key, value, expires_at)` shape serves list payloads now and detail/trailer payloads later (PRD §13's 1h / 24h TTLs are just different `ttl` arguments: `LIST_CACHE_TTL` / `DETAILS_CACHE_TTL`). Keys are namespaced strings, e.g. `tmdb:list:{list_id}:{page}`.
- **Epoch float for expiry, not a `DateTime` column.** Avoids SQLite's naive/aware datetime serialisation pitfalls and makes expiry a trivial tz-free numeric comparison. The clock is injectable so expiry is tested without sleeping.
- **Cache is an optional dependency of `MovieService`.** Passing `cache=None` falls back to live calls; this keeps the service unit-testable without a DB and leaves existing tests untouched. The real cache is built from the request-scoped session in the `get_movie_service` route dependency.
- **Manual refresh = `force_refresh` bypass.** A per-list Refresh button issues `?refresh=true`, which skips the cache read and rewrites the entry. For Top Rated, refresh propagates to each aggregated source list.
- **Expired-on-read pruning, no background sweeper.** Stale rows are deleted when next read (KISS, ADR-005); a scheduled cleaner is unnecessary at v1 scale.

Rationale: the generic table keeps the schema minimal while covering all v1 caching needs, and the optional-injection design preserves the typed, testable service boundaries from ADR-002/ADR-003.

## ADR-010: Radarr read integration — status mapping and merge

Read Radarr state through a `RadarrClient` (HTTP only) + `RadarrService` (logic), mirroring the TMDB client/service split (ADR-003).

Decisions:

- **Auth via `X-Api-Key` header**, not a query param, so the key never lands in a URL or log line (PRD §16).
- **Status precedence** (`status_from_radarr`): `hasFile` → `Downloaded` (wins regardless of monitored flag); else `monitored == false` → `Unmonitored`; else `monitored == true` → `Missing`; else `Unknown`. A downloaded-but-unmonitored movie reads as `Downloaded` because the file is what the user cares about. Missing/ambiguous fields fall back to `Unknown` rather than raising.
- **Match on `tmdbId`.** Blip's lists are TMDB-sourced, so the library is reduced to a `{tmdbId: RadarrStatus}` map; library entries without a `tmdbId` are skipped (unmatchable). `Movie.radarr_status is None` means "not in Radarr" and is the single signal both the desaturation/badge (M5) and the Add buttons (M7) key off.
- **Merge in the route, fail-soft.** The route fetches the page, then `RadarrService.annotate()` mutates the movies in one library call. A Radarr `httpx.HTTPError` is logged and swallowed (`_annotate_radarr`) so an outage degrades to "no status shown" instead of a broken page (PRD §15). `RadarrService` is an *optional* dependency — `None` when base URL/key are unset — keeping `MovieService` and existing tests independent of Radarr.
- **No Radarr caching in v1.** The library is fetched once per `/movies` request; a TTL cache (reusing `CacheService`) is deferred unless it proves heavy (KISS, ADR-005).

`quality_profiles()` / `root_folders()` are exposed now (tasks 4–5) but consumed by the settings (M6) and add (M7) milestones.