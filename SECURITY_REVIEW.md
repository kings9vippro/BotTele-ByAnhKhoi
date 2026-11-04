# Security review — 2026-11-04

Scope: targeted verification at `12ccb93`; this is not a complete repository audit.
The requested handoff document was not accessible in this environment.

## Confirmed and addressed on this branch

- Legacy API, account, task, and file routes lacked a shared authentication
  check. A request could reach handlers without a dashboard session. The shared
  middleware now requires a dashboard session or verified Telegram initData;
  public image assets and provider webhook routes remain available as needed.
- Cookie-authenticated cross-site mutation requests are blocked when the browser
  supplies a cross-site Fetch Metadata header or a mismatching Origin.
- API rate limiting previously used a 260-entry deque with a 320-request threshold,
  making the threshold unreachable. The capacity now matches the threshold.
- Existing login implementations and user data are unchanged.

Reproduced before the fix and verified after it in `tests/test_security_boundary.py`.
The Python 3.11.9 suite, startup structure check, and the existing mocked and
authenticated-browser Mini App tests passed on an isolated local server.

## Remaining risks and operational actions

- A Telegram bot token fallback is present in a tracked public repository file.
  Treat it as exposed: rotate it through BotFather and configure the replacement
  as a secret environment variable on Render. Removing it from the current file
  alone does not revoke old tokens or remove Git history. This branch does not
  change the token because the owner previously requested it be preserved.
- API rate limits derive client IP from `X-Forwarded-For`; unless the upstream
  proxy reliably overwrites that header, clients can spoof their apparent IP.
  Fixing this safely requires the actual trusted proxy topology.
- Session-based POST protection checks Origin/Fetch Metadata when present; it
  is not a full synchronizer-token CSRF design for clients omitting both headers.
- Live Render, official provider logins, platform rate limits, and externally
  configured OAuth redirect URLs have not been verified.
- For reverse proxies, confirm the app receives the correct HTTPS scheme and host;
  otherwise the Origin comparison may reject legitimate dashboard operations.
- `AUDIT_V4.md` lists additional architecture, task-state and frontend work that
  this targeted change does not claim to complete.
