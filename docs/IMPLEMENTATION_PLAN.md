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

- Milestones 1–11 complete. Two post-milestone HTMX v2 bug fixes applied (commits `230d6b7`, `1fa924c`) — see ADR-018 in docs/DECISIONS.md for the rules and rationale.
- Desktop genre controls now match the mobile pattern: each element owns its own HTMX attributes (`hx-get`, `hx-trigger`, `hx-include`); avoid the `from:` modifier in HTMX v2.