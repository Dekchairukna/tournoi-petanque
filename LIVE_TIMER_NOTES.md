# Live Board shared countdowns

- Open `/live`, select events, and use the countdown controls. Each event has its own timer. The bulk toolbar operates on selected events the signed-in operator can manage.
- `start` begins a fresh countdown using the entered minutes/seconds; `set` changes the duration without starting; `pause`, `resume`, and `reset` act on the saved countdown. Reset stops the clock and restores its saved duration.
- Other devices open `/live-board?events=...` on **the same server**, not their own localhost. No login is required to display the clock. Control requires an administrator with event access.
- Updates are fetched every 2 seconds; local display counts between updates using a monotonic clock and server remaining time. Network delays can cause a small difference between screens. A disconnected display reports that it is using its last received state.
- `live_event_timers` stores each deadline, paused remaining time, duration, and version in the shared application database. Existing startup `db.create_all()` creates this new table. Restart the application after installation; all workers must share one database and synchronized server clocks. No existing event or score columns are changed.
- Timer commands use one transaction and deadline for bulk operations. Stale commands from another controller return 409 and require checking the refreshed state. Viewer pages never issue commands. Timers do not change scores or advance rounds.

Validation: `python3 -m unittest discover -s tests -p test_live_timers.py` (isolated in-memory database). Browser validation uses disposable events on an isolated local preview server.
