# Blip

Blip is a LAN-hosted movie discovery app for browsing movie lists and adding selected movies directly to Radarr.

The app uses:

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLite
- HTMX
- Alpine.js
- Tailwind CSS
- Docker Compose

See:

- `docs/PRD.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/DECISIONS.md`

## Local development (venv)

Docker is the primary run path, but the app runs fine directly on your machine
for local development. You need Python 3.12+.

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. Install the project (with dev/test dependencies)

```bash
pip install -e ".[dev]"
```

The `-e` (editable) install means code changes are picked up without
reinstalling. The `[dev]` extra adds `pytest`.

### 3. Configure environment (optional for now)

```bash
cp .env.example .env
```

Settings fall back to sensible defaults, so `.env` is optional until TMDB/Radarr
integration lands. Locally the SQLite database is created at `./data/blip.db`
(auto-created on startup; the `data/` directory is gitignored).

### 4. Run the dev server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Then open:

- App: <http://localhost:8080/>
- Health check: <http://localhost:8080/health>

`--reload` restarts the server automatically when you edit code.

## Running tests

```bash
pytest
```

(Run inside the activated venv, or use `.venv/bin/pytest` without activating.)

## Running with Docker

The supported deployment path:

```bash
docker compose up -d
```

This serves the app on the port from `BLIP_PORT` (default `8080`) and persists
SQLite data in a named Docker volume.

## Development goal

Build this project incrementally in small vertical slices. Do not scaffold unnecessary features before proving the core TMDB and Radarr integrations.