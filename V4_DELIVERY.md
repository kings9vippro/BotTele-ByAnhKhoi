# V4 delivery record · 2026-11-05

Author: Dev Anh Khôi. Runtime version: 2.0.0. Branch: `codex/v4-delivery`.
This record distinguishes local evidence from live platform verification. The
previous `AUDIT_V4.md` is the baseline audit checkpoint; it is not a release
certificate. No user database, credential or production account was used.

## Source and configuration reviewed

Runtime/entry: `app.py`, `glaze_app.py`, `bot_settings.py`, `get_ck_im_zalo.py`,
`zalo_login.py`, `zalo_lag_engine.py`, `task_control.py`, `app_storage.py`,
`command_catalog.py`, `miniapp_oauth.py`, `official_integrations.py`,
`durable_tasks.py`, `control_plane.py`. Deployment/configuration:
`gunicorn.conf.py`, `render.yaml`, `requirements.txt`, `runtime.txt`,
`Procfile`, `.gitignore`, `scripts/verify_startup.py`. Frontend:
`templates/miniapp.html`, `static/control.css`, `static/control.js`,
`static/viet_hits.json`, legacy
Mini App assets and browser tests. Tests: every `tests/test_*.py` plus
`tests/control-browser.cjs`. This was syntax and focused behavior/source review,
not a credible claim that every line of the legacy 17k-line runtime was
manually audited. Binary Zalo core and real production data were not audited.

## Causes found and changes made

| Cause | Correction / scope |
|---|---|
| Retired Discord anti-ban stub still called by global stop and shared Zalo task setup | Removed shared-path calls; old Discord user-token automation and Facebook endpoints are retired. Historical database rows remain intact. |
| API rate bucket retained only 260 entries but blocked at 320 | Retains 320; expanded authorization across `/api`, `/task`, `/account`, `/file`; Origin/Sec-Fetch checks for browser mutations. |
| Unowned Zalo accounts were visible to delegates; relinking could transfer ownership | Root-only visibility of unowned rows and rejection of cross-owner relinks. |
| QR and group callback exported session credentials into chats | QR completion sends a receipt without cookies/token; export callback is private-chat-only and only for Zalo. |
| Global stop could be called by delegates; Mini App stop loop skipped hidden tasks | Root-only legacy global controls; queue has one transactionally scoped `stop_all(owner)` API. |
| Cleanup removed all old image assets | Only owned temporary filename prefixes with known image extensions are candidates. |
| Legacy web command reported success without dispatch | Rejects missing Zalo account and failed/unsupported dispatch. |
| Legacy Zalo verification called a cookie-shaped string “alive” | Requires actual live probe success before claiming verification. |
| Mini App polling/recreated view caused stale data and resets | Eight-panel Mini App with signed data requests, SSE state updates, bounded event history, native touch scroll snapping, real task actions, upload/selection of text files and task detail sheet. |
| Unbounded/untracked cross-channel notifications | SQLite queue with atomic 1–5 channel submission, five bounded workers, owner/channel constraints, persistent state, Retry-After and UNKNOWN outcome on ambiguous delivery. It is only for finite authorized webhook notifications, not a replacement of legacy Zalo tasks. |
| Telegram transport exceptions can include bot tokens in URLs | Transport, polling, update and status errors now expose only a generic failure and exception type, rather than raw exception text. Old tokens in Git history still require revocation. |
| Stop and status commands shared a saturated ordinary update pool | Telegram stop and task controls now use the reserved interactive pool. This does not interrupt a network request already in flight or guarantee response time. |
| Mini App task launch silently chose every Zalo account and lost box names | The Zalo screen now selects one enabled account and up to five cached groups; the server checks that each group belongs to that account before launching, then records the selected account and group names in the task. The legacy launch form remains available for existing clients. |
| Zalo account updates could reconcile listeners concurrently | Account/listener reconciliation now uses one lock; failures report an error type without exposing session details. |

## Architecture

Telegram commands and Mini App → server authorization → shared service
(`control_plane.py`) → SQLite task/event tables (`durable_tasks.py`) → five
workers → official Discord webhooks. Telegram's `/discord_login` starts the
same owner-scoped OAuth service as Mini App. OAuth uses Discord's authorization
code grant with state, one-use launch link, browser binding, issuer check,
encrypted tokens, owner-scoped upsert and revocation. Optional
`DISCORD_OAUTH_PKCE=1` adds an encrypted, per-attempt S256 verifier without
changing the existing confidential-client grant by default. The `identify` grant
only proves identity. Webhook messages appear as a webhook, never as the
linked personal Discord account. Existing Zalo authentication and listener
paths remain, with active startup limited to Zalo rows. Optional official
Discord Bot integration remains separate and is not needed for OAuth.

## Telegram command registry

`/start`, `/menu`, `/help`, `/miniapp`, `/accounts`, `/discord_login`,
`/discord_accounts`, `/discord_status`, `/discord_logout`, `/zalo`, `/tasks`,
`/task_status`, `/task_pause`, `/task_resume`, `/task_stop`, `/task_retry`,
`/channels`, `/send`, `/send_multi`, `/delay`, `/performance`, `/logs`,
`/settings`, `/system` are in the shared V4 registry and BotFather command
registration. Legacy Telegram handlers retained: `/files`, `/sticker`, `/qr`,
`/addck`, `/status`, `/checkzalo`, `/stopall`, `/addid`, `/delid`, `/listid`
and aliases in `get_ck_im_zalo.py`. The Mini App also lists supported Zalo
in-chat commands from `command_catalog.py`. The legacy runtime has other
in-chat aliases; a complete single-registry migration is still open.

## Mini App screens and interactions

Overview (real counts, workers, channel count, API latency, throughput and
event chart), Accounts (Zalo + linked Discord), Discord (official sign-in,
webhooks, finite send), Zalo (QR, cookie/IMEI, text files), Tasks (live cards,
pause/resume/stop/retry/details), Activity (bounded event history), Music
(Spotify's official Hot Hits Vietnam catalog and on-demand embed), Settings
(theme, OAuth app config, command list, storage status). Native scroll-snap
follows horizontal finger motion; each panel retains its own vertical scroll
and form state. Buttons have press/focus/loading/disabled states. The bottom
sheet has drag handle, Escape and confirmation. Theme follows Telegram when
available; reduced-motion settings remove decorative animation. SSE refreshes
task state without a full page reload. UI is responsive at 320, 390, 768 and
1280 px in Chromium. Spring constants, pull-to-refresh, all long-press menus,
focus trap, Telegram Main/Secondary buttons and real-device frame rate are
not verified/complete; do not advertise them as shipped.
The settings panel also offers locally persisted larger, heavier text and
three accent colors; these controls affect only the current browser/device.
The music tab shows ten verified Spotify links from the editorial Hot Hits
Vietnam playlist, checked on 2026-11-05. Spotify did not provide engagement
counts, so their order is not a numerical popularity ranking. The official
player loads only after a tap; actual playback depends on Spotify's account,
licensing, region and embedded player behavior. SSE permits eight concurrent
streams while Gunicorn retains request threads for bot controls.

An authorized Telegram user can now access only their own Discord identity,
webhook channels and notification tasks in the signed Mini App. Zalo accounts,
files and global settings remain root-only. The server verifies the signed
Telegram user against the authorization table; hiding controls in JavaScript
alone is not treated as authorization. Task cards retain focus across changed
snapshots and show IDs, status, attempts and the latest error. Bounded event
history reports a reset when a reconnect cursor falls behind the retained
window, allowing the client to replace stale events.

## Local verification (test-only credentials and no external API calls)

- `python scripts/verify_startup.py`: Python 3.11 syntax and entry checks pass.
- `python -m unittest discover -s tests -p 'test_*.py' -q`: 108 tests passed
  after scoped Mini App authorization, PKCE and SSE resync work, with
  `DISABLE_TELEGRAM_BOT=1`, `DISABLE_BACKGROUND_WORKERS=1`, test-only token
  and key. Re-run on final commit before deployment.
- `node --check static/control.js`: passed.
- `node tests/control-browser.cjs` against local Gunicorn/Chromium: passed
  eight tabs, Spotify catalog and embed shell, persistent form, light theme,
  dialog/Escape, saved text file,
  horizontal touch gesture, vertical gesture isolation, responsive widths,
  authenticated API and retired routes. No real Telegram device was used.
- `PYTHONPATH=. python scripts/benchmark_notifications.py`: local 25-job,
  five-channel, 40 ms mock API, three runs each: one worker median 1.049 s
  (range 1.044–1.054); five workers median 0.240 s (0.229–0.246).
  This compares local worker counts, not before/after production throughput.

## Deployment configuration and limits

Use Python 3.11 and `gunicorn app:app --config gunicorn.conf.py`. Set
`TELEGRAM_BOT_TOKEN` to a **new rotated token** in Render environment;
`TELEGRAM_ADMIN_ID`, stable `SECRET_KEY`, HTTPS `OAUTH_PUBLIC_BASE_URL`,
`DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` and a stable Fernet
`OAUTH_ENCRYPTION_KEY`. Register
`https://<your-host>/oauth/callback/discord` in Discord Developer Portal.
The Mini App can also save the Discord app configuration encrypted with a
stable `SECRET_KEY`; changing either encryption key invalidates stored
connections. The tracked token fallback has been removed from current source,
but remains public in Git history: code cannot revoke it; rotate via BotFather
before production. The bot and Mini App now require `TELEGRAM_BOT_TOKEN`
explicitly in the environment. `DISCORD_OAUTH_PKCE=1` enables S256; verify
the confidential-client/PKCE combination in a live Discord consent test.

Provide durable `DATABASE_PATH` and `APP_DATA_DIR` storage; Render Free's
ephemeral disk can lose account/task data on redeploy. Keep Gunicorn at one
application worker because this SQLite queue starts its workers in-process.
Discord OAuth login alone cannot send personal-account messages. Official
webhooks require administrator permission for each channel and obey Discord's
`Retry-After`. The exact outcome after a network failure following an external
send may be unknowable; UNKNOWN tasks are not automatically replayed.
Facebook and private Discord token/registration/captcha flows are absent from
active use. Historical records were not erased.

## Open release criteria

Live Discord OAuth consent, webhook sends, Zalo QR/listener behavior, Render
deploy, Spotify playback in Telegram's mobile webview, Telegram mobile
gestures/haptics, persistent disk migration, and
cross-account production load have **not** been tested. Legacy Zalo workers
are not migrated to the new persistent scheduler. Legacy dashboard CSRF still
relies on SameSite/Origin/Sec-Fetch rather than a full per-request token; the
public tracked bot token must be rotated. Delegated Mini App Zalo management
is intentionally unavailable until a separately scoped backend is built.
Dependencies have lower bounds but no checked lockfile. No claim of zero lag, exactly-once delivery, 60 FPS or
complete V4 release is made without those checks.

Official references checked: [Discord OAuth2](https://docs.discord.com/developers/topics/oauth2)
and [Discord rate limits](https://docs.discord.com/developers/topics/rate-limits).
