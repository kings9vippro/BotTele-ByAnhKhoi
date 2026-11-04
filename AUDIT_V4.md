# V4 audit checkpoint — 2026-11-04

Status: INCOMPLETE. This is an initial source audit and a verified security repair,
not a V4 delivery certificate. Baseline: d06b31f. No production accounts were used.

## Evidence and root causes

| Area | Evidence | Consequence / required change |
|---|---|---|
| Authentication | `glaze_app.py`: `login_discord_reg_session`, `DiscordTokenGetter`, `DiscordImmortalRegTool`; Telegram imports in `get_ck_im_zalo.py` | Official OAuth coexists with password/user-token/registration paths. Removing only UI cards would leave these paths reachable. Retire their handlers and worker consumers as one migration. |
| Facebook | OAuth provider, `official_integrations.py`, `MessengerClient`, `MessengerRealtimeListener`, Telegram credential handlers | Removal requires legacy runtime and Telegram changes, not just deleting the Page webhook. Retain old database records without loading them into active workers. |
| Secret disclosure | `generate_totp_rfc6238` forwarded malformed secrets to a third-party HTTP service | Fixed: invalid input fails locally. Added RFC 6238 vector and no-network regression tests. |
| Worker pressure | Telegram pool 32 + interactive pool 4; runtime priority pool 32, two interactive pools 4 each, sticker pool 2, typing pool 8; additional scanning pools | Thread count alone is not backpressure. ThreadPoolExecutor pending submission queues are not bounded by max_workers. Profile and bound submission at producer boundaries; preserve prompt administrative cancellation. |
| Task persistence | `task_control.py` joins RAM dictionaries; `glaze_app.py` periodically flushes dirty task rows | Existing cooperative cancellation is not a persistent fair scheduler. Need atomic claims, owner/channel limits, durable attempts, and explicit unknown outcome recovery. Do not automatically replay uncertain sends. |
| Menu | `command_catalog.py` contains 14 documentation entries; Telegram and runtime retain separate handlers | Not a verified unified handler registry. Extract actual handlers and permissions before advertising target commands. |
| UI synchronization | `static/miniapp.js` uses interval polling and hides/shows panes | Not SSE/WebSocket, not gesture-following swipe tabs, and no evidence for spring motion/60 FPS. Implement incremental events after authoritative backend state exists. |
| Storage | SQLite WAL via `app_storage.py`, Render deployment | WAL helps concurrent reads but does not make Render ephemeral storage permanent. A durable volume/database must be provisioned before promising restart/redeploy retention. |
| Dependencies | `requirements.txt` uses minimum versions without upper bounds/lock | Rebuilds can resolve different dependencies. Capture and validate a compatible dependency set before locking. |
| Uploaded tools | ZIP contains solver/captcha.py, token_checker.py, proxy_checker.py and core/joiner.py; userscript reads Discord client storage tokens and offers exporting them | Not part of the official OAuth flow. Not executed or integrated. Registration, CAPTCHA circumvention and user-token collection are excluded. |

## Source coverage in this checkpoint

Syntax/startup structure checks: all production Python files via
`scripts/verify_startup.py`. JavaScript syntax: `static/miniapp.js`,
`tests/miniapp-browser.cjs`, `tests/miniapp-live.cjs`.

Targeted source inspection: `app.py`, `app_storage.py`, `miniapp_oauth.py`,
`official_integrations.py`, `task_control.py`, `command_catalog.py`,
`glaze_app.py`, `get_ck_im_zalo.py`, `gunicorn.conf.py`, `requirements.txt`,
`static/miniapp.js`, `templates/miniapp.html`, `tests/test_oauth.py`,
`tests/test_management.py`. Worker symbol searches also covered
`zalo_login.py` and `zalo_lag_engine.py`.

This does not claim line-by-line review of all 33,000+ source lines. C++,
assets, every legacy route, production schema/data, Render logs and live
platform behavior have not received a complete V4 audit.

## Verified repair

Changed `glaze_app.py`; added `tests/test_totp_privacy.py`.
The new malformed-secret test failed before the repair and passed after it.
Full isolated Python 3.11.9 suite: 74 tests passed in 4.315 seconds.
Production syntax/startup structure and the three JS syntax checks passed.
Test elapsed time is not a command latency or throughput benchmark.

## Remaining delivery sequence

1. Retire Facebook and legacy Discord password/self-bot/registration handlers,
   callbacks, startup consumers and UI; preserve stored records for explicit
   owner-controlled export/deletion. Add negative route and startup tests.
2. Expose official Discord OAuth through Telegram commands, with owner isolation,
   revocation/expiration handling and callback notification. Configure the real
   Discord application and HTTPS redirect URL. Never collect a Discord password.
3. Implement authorized webhook channels and a bounded persistent queue with
   fair per-owner/channel dispatch. Test five independent channels, failure
   isolation, Retry-After, cancellation, pause/resume and uncertain delivery.
4. Build an actual handler-backed command registry and shared application services.
5. Add backend events/metrics, then build the requested dashboard, gestures,
   dialogs, sheets and theme support with accessible fallbacks.
6. Measure baseline vs changed implementation with a documented workload;
   perform browser, auth, concurrency, recovery and production build checks.

No new dashboard, webhook sender, persistent scheduler, complete Facebook removal,
complete command list, load benchmark or production OAuth verification is claimed
by this checkpoint. Existing UI tests from earlier commits are not evidence for
the new V4 UX requirements.

## Deployment inputs still needed

Public Render/Mini App HTTPS URL and Discord Application ID; Client Secret must
be configured in server secrets, never pasted into chat or committed. Live OAuth
requires the user to approve Discord's official consent screen. Authorized
webhook channels and persistent storage must be available for production tests.
These external inputs do not replace the remaining implementation work above.
