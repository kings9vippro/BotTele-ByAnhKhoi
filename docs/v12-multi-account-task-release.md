# V12 — Zalo multi-account listener recovery and scoped task controls

## Confirmed code-level defects and fixes
- The Zalo account importer formerly updated the first matching UID even when an incoming session had a distinct IMEI. It now matches existing sessions by IMEI first and preserves separate device sessions under the same owner. It rejects cross-owner UID conflicts.
- Listener reconciliation used one exception boundary around all accounts and skipped later accounts when one failed. Each listener now has its own failure isolation and operational status, with no cookie values logged.
- Listener deduplication now uses IMEI/device identity before UID hints, so two separate IMEIs with the same stale UID hint are not silently suppressed. Exact duplicate IMEI sessions remain deduplicated and expose a non-secret conflict reason.
- The Mini App accounts API adds `listener_health` (running, stopped, worker_unavailable, duplicate_imei or listener_start_failed); the UI displays it instead of saying “saved” for a non-running account.

## Telegram commands
- `/task_accounts [page]` shows owner-authorized Zalo ACC numbers, account names, live listener health and a count of active tasks.
- `/tasks <acc_id> [page]` and `/tasks ACC-<id> [page]` show real task state, owner-scoped and paginated, with inline navigation and manual refresh buttons. `/tasks all [page]` shows all authorized tasks.
- `/dsbox ACC-<id> [page]` uses the same internal ACC reference. ACL checks still use database ownership, not user-submitted credential values.
- Task state remains process-local when the engine only supports RAM persistence; cross-cookie tasks cannot be stopped independently.

## QR and credential handling
- On successful Zalo QR login the initiating account receives a full IMEI only in their own private Telegram chat. Group chats receive a masked IMEI.
- An explicit, private-only receipt document includes the internal ACC handle, full IMEI, UID and command examples. **It does not contain reusable cookie/session values**, and its Telegram document is protected from forwarding.
- `ACC-<id>` is an internal reference to a saved authenticated session, not a shortened Zalo cookie. Removing characters from a raw session cookie does not preserve its validity.
- No third-party session cookie exports or root-only raw-cookie access have been added.

## Mini App and music
- Five mobile bottom navigation icons use identical 24×24 SVG geometry; the active icon no longer scales up or shifts.
- Account cards show listener health. Zalo views have more legible bold labels and body text.
- Spotify remains the official playlist Embed with `encrypted-media` allowed. Full playback is controlled by Spotify user entitlements and WebView compatibility; opening the track or playlist in Spotify is the supported full-track option.

## Security and deployment
The source revision inspected before V12 had a real token-shaped fallback in `bot_settings.py`. V12 removes it without copying its value. **Before deploying, verify that Render already has the correct `TELEGRAM_BOT_TOKEN` secret in Environment.** The current hosting setting has not been read or modified in this change. Removing the fallback without a host secret will stop Telegram polling even if the web health endpoint returns 200. Rotate any previously exposed token using BotFather.

## Test status and limitations
- 232/232 Python unit tests PASS with synthetic credentials and disabled external provider jobs.
- Python startup verifier and Gunicorn configuration PASS.
- JavaScript and browser-test syntax PASS.
- Mobile Chromium end-to-end PASS against isolated local Flask with two synthetic accounts, protected auth gate, navigation icons, task selection, box pagination, music Embed shell and gestures.
- Targeted scan of 9 changed source files: no Telegram-token-shaped literal.
- `scripts/check_secrets.py` could not execute in the isolated browser container because that environment has no `git` binary. GitHub CI must run the repository-wide scanner.
- Actual provider Zalo cookie validity, Render storage persistence, Telegram live command responsiveness and Spotify full-length playback remain **NOT LIVE VERIFIED**.

Do not claim sub-second latency or successful production delivery without provider/hosting measurements.