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

## Handoff notes

- Milestones 1–11 complete.
- Full milestone details now live in `docs/ARCHIVES.md`.
- Mobile: hamburger drawer with all nav items (tabs, genre/rating, TMDB, Settings).
- Desktop: two-row header — brand/TMDB/settings above, tabs + genre controls below.
- Settings page has drawer tabs too (redirects to `/?list=X` since `#movie-list` absent).
- Alpine state on `<body>`; mobile controls use `-mobile` ID suffix; `x-cloak` prevents flicker.