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