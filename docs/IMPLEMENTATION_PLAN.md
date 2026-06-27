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

- Milestones 1–11 complete. Two post-milestone bug fixes applied.
- **Fix #1** (commit `230d6b7`): `hx-trigger="load"` on `#movie-list` doesn't fire when HTMX is deferred alongside Alpine. Replaced with `x-init="$nextTick(() => htmx.ajax(...))"` in `index.html`.
- **Fix #2** (commit `1fa924c`): HTMX v2.0.3 requires filters `[expr]` immediately after event name, before modifiers. `change from:#genre-select[this.value != '']` was silently broken — moved triggers directly to `<select>`/`<input>` elements.
- Desktop genre controls now match mobile pattern: each element owns its own HTMX attributes (`hx-get`, `hx-trigger`, `hx-include`). Avoid `from:` modifier in HTMX v2.