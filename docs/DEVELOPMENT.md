# Local Development

Blip runs fine directly on your machine for local development. You need Python 3.12+.


## Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

## Install the project

```bash
pip install -e "."
```

The `-e` (editable) install means code changes are picked up without reinstalling.

## Configure environment (optional)

```bash
cp .env.example .env
```

Settings fall back to sensible defaults, so `.env` is optional until TMDB/Radarr integration is needed. 
Locally the SQLite database is created at `./data/blip.db` (auto-created on startup; the `data/` 
directory is gitignored).

## Run the dev server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Then open:

- App: <http://localhost:8080/>
- Health check: <http://localhost:8080/health>

`--reload` restarts the server automatically when you edit code.
