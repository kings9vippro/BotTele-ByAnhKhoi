# Development progress · V5

## Completed

- Hardened Mini App SSE with bounded jittered reconnects, stale-stream detection,
  request cancellation, correlation IDs and resumable cursors.
- Persisted durable task terminal states across shutdown races and serialized
  owner-fair queue claims without creating unbounded workers.
- Added compact icon-only bottom navigation with accessible labels, reduced-motion
  support and browser regression coverage.
- Scoped sticker media requests to both Telegram user and chat so unrelated media
  cannot be consumed by another conversation.
- Retired Facebook/Messenger web intake and rejected Discord passwords, MFA fields
  and user tokens; Discord linking remains official OAuth2 only.
- Removed the third-party Zalo credential fallback and routed the watchdog through
  the public `/healthz` probe.
- Removed the tracked Telegram token fallback and added a CI secret regression gate.
- Aligned the music catalog with the official Spotify playlist/embed contract.

## Remaining / explicitly unverified

- Rotate the historical Telegram token through BotFather; old commits cannot be
  revoked by source changes.
- Encrypt existing plaintext Zalo credential columns with a deploy-managed key and
  migration/rollback procedure.
- Verify live Discord OAuth, authorized webhooks, Zalo QR/listeners, Spotify mobile
  playback and persistent Render storage with staging credentials.
- Legacy Facebook/Messenger compatibility symbols remain in the monolith for data
  compatibility, but public routes and account intake return HTTP 410.

## Delivery status

V5 was merged to `main` through PR #4 at merge commit
`b94325bba181b15ee3577e56e3db7fa7da1aafe3`. The implementation branch remains
`codex/v5-production-rebuild` and is retained for remote traceability.
