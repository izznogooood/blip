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
- HTMX v2 trigger filters `[expr]` must come immediately after the event name, before modifiers like `from:`. Prefer placing triggers directly on the element and omitting `from:`.
- Avoid `hx-trigger="load"` when HTMX is deferred alongside Alpine — the `setTimeout(0)` callback can be swallowed by Alpine's initialization. Use `x-init="$nextTick(() => htmx.ajax(...))"` instead.

## Workflow

v1 (milestones 1–11) is complete. Default to the lightweight path; use the milestone
path only when starting a planned milestone.

**Default (bugfix / small feature):**
1. State the files you'll touch.
2. Implement. Run `pytest -q`.
3. Report: files changed, commands run, assumptions.

**Milestone path (starting a planned milestone):**
1. Read the current milestone section in docs/IMPLEMENTATION_PLAN.md. State files to create/change.
2. Implement only that milestone. Run `pytest -q`.
3. On completion: mark milestone ✅ in the plan, move details to docs/ARCHIVES.md,
   leave max 5 one-line handoff bullets.

**Either path:** a new architectural choice → add a short ADR (≤10 lines) to
docs/DECISIONS.md and a one-line entry to its index.

## Out of scope (v1)

Auth, multi-user, mobile app, Jellyfin, scheduled adding, RT scraping,
indexer integration, approval workflows, bulk adding, SPA.