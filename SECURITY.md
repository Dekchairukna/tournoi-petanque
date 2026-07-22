# Security configuration

## Required before starting

Copy `.env.example` to `.env` and replace every example secret. Never commit
`.env`, a production database, uploaded score sheets, or exported user data.

This secured release deliberately refuses to start when the protected `yagami`
account does not exist and `YAGAMI_SUPERADMIN_PASSWORD` is missing. It also
refuses to continue when either legacy account still uses a password that was
previously published in source. Supply `SUPERADMIN_PASSWORD` and
`ADMIN_PASSWORD` once to rotate those credentials.

After the first successful start, remove the three account-password variables
from the hosting dashboard. Passwords are not reset on later restarts. Keep
`SECRET_KEY` stable and secret.

For an HTTPS deployment set `COOKIE_SECURE=1`, `FLASK_DEBUG=0`, and list only
trusted, exact origins in `ALLOWED_ORIGINS`. Do not use `*`.

## Operational checks

- Back up the database outside the public web directory.
- Review reverse-proxy access logs for repeated `/login`, 403, 404 and 429.
- Rotate credentials immediately if a source archive or database is shared.
- Apply dependency security updates regularly and retest the tournament flow.
- Give ordinary organizers `admin`; reserve `superadmin` for system owners.
