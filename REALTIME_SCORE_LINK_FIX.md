# Realtime score link fix

- Removed old round live reload usage from round page.
- Keeps Socket.IO score updates between devices.
- Adds `/event/<event_id>/round/<round_no>/scores-json` lightweight fallback so another device updates fields without full page refresh even if socket room join fails.
- Score events are emitted only to the event/round room and event room, not global broadcast.
- Score save skips DB commit when the score did not change.
