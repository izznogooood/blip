# Blip Implementation Plan

Build in small vertical slices. One milestone per session. Keep the app runnable after each milestone.

## Progress

| Milestone | Status |
|---|---|
| 1. Project skeleton | ✅ Complete |
| 2. TMDB list rendering | ✅ Complete |
| 3. List tabs and Load More | ✅ Complete |
| 4. SQLite caching | ✅ Complete |
| 5. Radarr read integration | ✅ Complete |
| 6. Settings | ✅ Complete |
| 7. Add and Add + Search | ✅ Complete |
| 8. Synopsis modal and trailer | ✅ Complete |
| 9. Polish and tests | ❌ Scrapped |
| 10. Genre dropdown | ✅ Complete |
| 11. Responsive Top Navigation | ✅ Complete |
| 12. Fix missing-movies search filter | ⬜ |

Status: ⬜ Not started · 🚧 In progress · ✅ Complete · ❌ Scrapped

## Active milestone

## Milestone 12: Fix missing-movies search filter — ⬜
Goal: Replace the broken `MissingMoviesSearch` command (which ignores `filterKey`/`filterValue`) with a two-step approach: query Radarr for monitored missing available movies, then search only those specific IDs.

### Context

Commit `cf3cdff` added `filterKey="status", filterValue="released"` to `MissingMoviesSearch`, but this does **not work**. Investigation revealed:

- The Radarr v3 `CommandResource` schema (OpenAPI spec) has **no** `filterKey`/`filterValue` fields. The command body only accepts `name`, `sendUpdatesToClient`, `updateScheduledTask`, `completionMessage`, `trigger`, and `manualRun`.
- A third-party Go client library (`SkYNewZ/radarr`) defines `filterKey`/`filterValue` as top-level JSON fields, but its `MissingMoviesSearch` function is a **stub** (`return nil`) — it was never implemented server-side. The filter concept was never merged into Radarr's command endpoint.
- When we send `{"name": "MissingMoviesSearch", "filterKey": "status", "filterValue": "released"}`, Radarr silently ignores the unknown fields and runs an **unfiltered** search of all monitored missing movies.
- Radarr's own UI "Search All" button on the Wanted → Missing page does **not** use `MissingMoviesSearch` either. It sends specific movie IDs via `MoviesSearch` after filtering the list client-side.
- `isAvailable` is the correct field for "can this movie be downloaded?" — a movie is available when its `physicalRelease`/`digitalRelease` date has passed, or 3 months after `inCinemas` if no release date exists.

Plan:
1. Add `RadarrClient.search_movies(movie_ids)` — wraps `POST /api/v3/command` with `{"name": "MoviesSearch", "movieIds": [...]}`.
2. Add `RadarrClient.get_missing_available_movies()` — fetches `GET /api/v3/movie`, filters for `monitored == true`, `hasFile == false`, and `isAvailable == true`.
3. Update `RadarrService.search_missing()` to call the two new methods: get filtered IDs, then send `MoviesSearch`.
4. Remove the dead `filterKey`/`filterValue` kwargs from `command()` and `search_missing()`.
5. Update `tests/test_radarr_command.py` to cover the new flow.

Files:
- `app/clients/radarr_client.py`
- `app/services/radarr_service.py`
- `tests/test_radarr_command.py`

Tests:
- `test_search_missing_filters_by_availability` — verify only monitored+missing+available movies are searched
- `test_search_missing_skips_unavailable_movies` — verify announced/in-cinemas movies are excluded
- `test_search_missing_handles_empty_result` — no available missing movies → no command sent

ADRs: Add ADR to `docs/DECISIONS.md` noting that Radarr's command API ignores unknown fields and `MoviesSearch` with explicit IDs is the correct way to do filtered searches.

## Adding a milestone

1. Decide the path: a minor feature or bugfix → use the prompt path (no milestone). Major or
   architectural work → add a milestone.
2. Add a row to the Progress table (next number, status ⬜). For a body of work spanning several
   slices, add a `### v2` group heading and a small cluster of rows (12, 13, …).
3. Copy the template below into **Active milestone** and fill in Goal/Plan/Files/Tests.
4. Build per CLAUDE.md's Milestone path. On completion: flip the row to ✅, move the filled-in
   spec from **Active milestone** to docs/ARCHIVES.md, reset Active to the placeholder, and leave
   ≤5 one-line handoff bullets.

## Milestone template

```
## Milestone N: <name> — ⬜
Goal: <one-line outcome; one runnable vertical slice>
Plan: <2–5 bullets of what to build>
Files: <files to create/change>
Tests: <what pytest coverage proves it works>
ADRs: <new architectural choices → add an ADR to docs/DECISIONS.md>
```

## Handoff notes

- Milestones 1–11 complete. Two post-milestone HTMX v2 bug fixes applied (commits `230d6b7`, `1fa924c`) — see ADR-018 in docs/DECISIONS.md for the rules and rationale.
- Desktop genre controls now match the mobile pattern: each element owns its own HTMX attributes (`hx-get`, `hx-trigger`, `hx-include`); avoid the `from:` modifier in HTMX v2.
- Title search: `GET /movies?query=` is a third mode of the movies endpoint (precedence query > genre_id > list), reusing the grid/Load More/modal/add pipeline. Backed by `TMDBClient.search` → `/search/movie` and `MovieService.search`. Search box in desktop nav + mobile drawer.