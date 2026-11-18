# Live Board shared countdowns

- Open `/live`, select events, and use the countdown controls. Each event has its own timer. The bulk toolbar operates on selected events the signed-in operator can manage.
- `start` begins a fresh countdown using the entered minutes/seconds; `set` changes the duration without starting; `pause`, `resume`, and `reset` act on the saved countdown. Reset stops the clock and restores its saved duration.
- Other devices open `/live-board?events=...` on **the same server**, not their own localhost. No login is required to display the clock. Control requires an administrator with event access.
- Updates are fetched every 2 seconds; local display counts between updates using a monotonic clock and server remaining time. Network delays can cause a small difference between screens. A disconnected display reports that it is using its last received state.
- `live_event_timers` stores each deadline, paused remaining time, duration, and version in the shared application database. Existing startup `db.create_all()` creates this new table. Restart the application after installation; all workers must share one database and synchronized server clocks. No existing event or score columns are changed.
- Timer commands use one transaction and deadline for bulk operations. Stale commands from another controller return 409 and require checking the refreshed state. Viewer pages never issue commands. Timers do not change scores or advance rounds.

Validation: `python3 -m unittest discover -s tests -p test_live_timers.py` (isolated in-memory database). Browser validation uses disposable events on an isolated local preview server.

## Live Board redesign (phase 1)

- `/live-board` now has one compact header (logo, event name, round, timers, board-style button), a table that fills the screen, and a slim footer (connection status, awaiting-draw note, page number).
- Board style lives in the link: `theme` (light, cream, dark, event), `per_page` (8, 10, 12, 16, 20, 24), `font` (s, m, l, xl), `lang` (th, en), plus the existing `pages` and `interval`. Invalid values fall back to defaults. KKU boards default to the KKU event theme in English; other boards default to the light theme in Thai.
- The "Board style" dialog previews changes live; Apply writes them into the URL (and this browser's storage) so the link can be copied to other screens.
- Admins who can manage an event see a clickable clock and a Start/Pause button on the board itself. The dialog sends the same `/live/timers/command` requests as `/live`, so every screen stays in sync. Viewers see only the clock.
- Page code: `templates/live_board.html`, `static/css/live_board.css`, `static/js/live_board.js`. `static/js/live_timers.js` is still used by `/live`.
- Count-up timers and per-event colour palettes are planned for phase 2 (they need new database columns).
