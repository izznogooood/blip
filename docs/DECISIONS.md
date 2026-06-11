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