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

Status: ⬜ Not started · 🚧 In progress · ✅ Complete · ❌ Scrapped

## Active milestone

None active — copy the template below to start one.

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