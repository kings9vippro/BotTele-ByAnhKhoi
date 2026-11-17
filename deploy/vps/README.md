# VPS deployment

Use one Gunicorn worker. The Telegram polling process and some Zalo tasks live
inside that worker; adding Gunicorn workers would create competing bot pollers
and split process-local task state. The worker has 16 request threads for
independent HTTP requests. Provider limits still apply.

1. Install Python 3.11 and system packages required by `requirements.txt`.
2. Extract the release into `/opt/bottele/current` and create a virtualenv there.
3. Install with `.venv/bin/pip install -r requirements.txt`.
4. Create user `bottele`, persistent directory `/var/lib/bottele` owned by that
   user, and `/etc/bottele/bottele.env` readable only by that user/root.
5. Put these values in the environment file (actual values stay private):
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_ID`, `SECRET_KEY`,
   `APP_DATA_DIR=/var/lib/bottele`, `DATABASE_PATH=/var/lib/bottele/database.db`,
   `PORT=5000`, `BIND_HOST=127.0.0.1`. Configure optional Discord OAuth
   secrets there as needed. `GUNICORN_THREADS` may be tuned from 4 to 32
   using measurements; it defaults to 16.
6. Copy `deploy/vps/bottele.service` to `/etc/systemd/system/`, run
   `systemctl daemon-reload`, `systemctl enable --now bottele`, and inspect
   `journalctl -u bottele -n 100` without sharing credentials.
7. Reverse proxy HTTPS to `127.0.0.1:5000`; update the Mini App URL and Discord
   OAuth redirect to the final HTTPS domain. Verify `/healthz`, bot readiness,
   a signed Mini App session, task visibility, and task stop before migration.

Migrate `database.db` together with its WAL/SHM files only after stopping the
old service, or use SQLite's online backup API. Copy the `uploads/` directory
as well. Keep a private backup. Process-local tasks cannot survive restart;
durable notification tasks require the persistent database path above.

`systemd` restarts the service after a crash or host reboot. A VPS, network,
provider API, and process-local tasks cannot be guaranteed to run without
interruption. Do not run the old Render instance with the same bot token: two
Telegram pollers can conflict.
