# Archived Milestones

## Milestone 10: Genre Dropdown

Goal: Add a genre dropdown alongside the existing list tabs so users can browse TMDB genres.

### Changes

- **`app/schemas/movie.py`** — Added `Genre` pydantic model
- **`app/clients/tmdb_client.py`** — Added `genres()` → `GET /genre/movie/list`
- **`app/services/movie_service.py`** — Added `genres()` (24h cache), `genre_movies()` with 180-day discover params, `_genre_params()` with optional `sort_by_rating`
- **`app/web/routes.py`** — `index()` fetches genres for template; `movies()` accepts `genre_id` and `sort_by_rating` query params; caption looked up server-side via `_genre_caption()`
- **`app/templates/partials/list_tabs.html`** — Genre dropdown and "By rating" checkbox in the tab bar; Alpine tracks `activeTab`, `activeGenre`, `sortByRating`; tab click resets all
- **`app/templates/partials/_load_more.html`** — Preserves `genre_id` and `sort_by_rating` in Load More URL
- **`app/templates/partials/movie_grid.html`** — Refresh button preserves genre/sort params

### Key decisions (ADR-016)

- Genres fetched live from TMDB, cached 24h.
- 180-day lookback window with `primary_release_date.desc` (default) or `vote_average.desc` (toggle).
- Not added to `MOVIE_LISTS` — separate browsing dimension, doesn't pollute Top Rated.
- Dropdown uses HTMX attributes (`hx-trigger="change[this.value != '']"`); sort checkbox uses `hx-include` paired with container-level `hx-trigger`.

### Tests added

- Genre model mapping (normal + missing name)
- Genre movie dispatch (discover, 180-day window, default sort, rating sort)
- Genre route (caption, Load More preserves genre_id)
