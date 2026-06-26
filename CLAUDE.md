# Blip — Claude Instructions

Blip is a LAN-hosted movie discovery app: browse TMDB lists, add movies to Radarr.

## Reading docs (IMPORTANT — token discipline)

- Do NOT read all docs up front.
- Read ONLY the current milestone's section in docs/IMPLEMENTATION_PLAN.md.
- Consult docs/DECISIONS.md or docs/PRD.md only when the milestone touches that area; prefer grep/targeted section reads over full-file reads.
- docs/ARCHIVES.md holds completed-milestone details — read only if you need history.

## Stack

Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, SQLite, httpx, pytest,
Jinja2 + HTMX + Alpine.js + Tailwind (CDN). Docker Compose is the run path.

## Rules

- One milestone at a time; app stays runnable after each. KISS.
- No React/Vue/Svelte/Next/Vite/npm pipeline.
- Modern typing (`str | None`, `list[str]`). Thin routes; HTTP in `clients/`, logic in `services/`.
- Never expose API keys to browser HTML or logs.

## Workflow per milestone

1. Read the current milestone section. Briefly state files to create/change.
2. Implement only that milestone. Run `pytest -q`.
3. Report: files changed, commands run, assumptions.
4. On completion: mark milestone ✅ in the plan, move its details to docs/ARCHIVES.md,
   leave max 5 one-line handoff bullets in the plan.
5. New architectural choice → add a short ADR (≤10 lines) to docs/DECISIONS.md.

## Out of scope (v1)

Auth, multi-user, mobile app, Jellyfin, scheduled adding, RT scraping,
indexer integration, approval workflows, bulk adding, SPA.