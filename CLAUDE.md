# Blip Claude Instructions

Blip is a LAN-hosted movie discovery app for browsing movie lists and adding selected movies directly to Radarr.

Read these files before planning or implementing:

- @docs/PRD.md
- @docs/IMPLEMENTATION_PLAN.md
- @docs/DECISIONS.md

## Core constraints

- Build incrementally by milestone.
- Do not implement multiple milestones at once unless explicitly asked.
- Keep the app runnable after every milestone.
- Follow the KISS principle.
- Prefer boring, maintainable, industry-standard code.

## Tech stack

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLite
- SQLModel or SQLAlchemy 2.x
- httpx
- pytest
- Jinja2 templates
- HTMX
- Alpine.js
- Tailwind CSS via CDN
- Docker Compose

## Frontend rules

- Do not use React.
- Do not use Vue.
- Do not use Svelte.
- Do not use Next.js.
- Do not use Nuxt.
- Do not use Vite.
- Do not introduce an npm build pipeline for v1.
- Use Jinja2 only as the server-side template renderer.
- Use HTMX for partial updates.
- Use Alpine.js only for small local UI state such as modals.

## Backend rules

- Use modern Python typing syntax:
  - `str | None`, not `Optional[str]`
  - `list[str]`, not `List[str]`
- Keep FastAPI routes thin.
- Put external HTTP integrations in `clients/`.
- Put business logic in `services/`.
- Use Pydantic models for typed API/data boundaries.
- Do not expose Radarr or TMDB API keys to browser-rendered HTML.

## Workflow

Before coding a milestone:

1. Inspect the current repo.
2. Identify the milestone from `docs/IMPLEMENTATION_PLAN.md`.
3. Explain briefly which files will be created or changed.
4. Implement only that milestone.
5. Run relevant tests.
6. Report files changed, commands run, and assumptions made.

On completing a milestone:

1. Update `docs/IMPLEMENTATION_PLAN.md`: mark the milestone complete in the progress table and check off its acceptance criteria (noting any caveats).
2. If the work resolved an open question or made an architectural choice, record it in `docs/DECISIONS.md` (as an ADR) and update `docs/PRD.md` §25 accordingly.
3. Keep these docs the source of truth so other sessions know the current state.

## Verification

Prefer deterministic checks:

- Run `pytest` after backend/service changes.
- Run formatting/linting tools if configured.
- Make sure `docker compose up` remains the primary run path.

## Product scope

Out of scope for v1:

- authentication
- mobile app
- multi-user support
- Jellyfin integration
- automatic scheduled adding
- Rotten Tomatoes scraping
- torrent/indexer direct integration
- request approval workflows
- bulk adding
- React/Vue SPA

