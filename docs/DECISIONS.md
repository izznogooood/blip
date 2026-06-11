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