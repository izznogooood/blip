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

## Development goal

Build this project incrementally in small vertical slices. Do not scaffold unnecessary features before proving the core TMDB and Radarr integrations.