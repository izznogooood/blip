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

## Handoff notes

- Milestones 1–10 complete.
- Full milestone details now live in `docs/ARCHIVES.md`.
- Use this file only for current state and next-step handoff.

## Current state

Active maintenance and itterative development. 

## Handoff — genre dropdown

- Genre dropdown in tab bar, fetches live from TMDB (cached 24h), 180-day window.
- "By rating" checkbox toggles sort between newest-first and highest-rated-first.
- `genre_id` and `sort_by_rating` preserved in Load More and Refresh.
- Detailed writeup in `docs/ARCHIVES.md`.
