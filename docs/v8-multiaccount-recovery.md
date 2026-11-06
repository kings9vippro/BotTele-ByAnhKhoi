# V8 — Incident: DNS, multi-account Zalo command isolation and task views

## Production finding — Mini App loading spinner

At inspection, the domain \`tech-pak.store\` returned DNS status **3 / NXDOMAIN** from both Google DNS and Cloudflare DNS; an HTTPS probe failed before reaching the server because the hostname did not resolve. The iOS Telegram spinner alone cannot identify a JavaScript or backend bug. **Fix domain registration, delegated nameservers and A/CNAME records first**, then verify the direct hosting URL and deployment SHA.

The DNS failure cannot be fixed with a GitHub commit. It requires the authorized domain/hosting owner. Do not redirect the Mini App to an unverified hostname. Check the BotFather menu button URL *after* the domain works.

## Zalo per-cookie changes

- \`.dsbox [page]\`, \`.listbox [page]\`, \`.dsnhom [page]\`: only the cookie that received the Zalo command is used for group discovery and replies, never the global group-ID union. Page size 12.
- Telegram \`/dsbox\`: show authorized Zalo accounts only; \`/dsbox <acc_id> [page]\` lists this cookie's cached groups with Previous/Next buttons. An uncached/stale account is refreshed asynchronously using its own saved account session (2 concurrent global requests maximum, 35-second cooldown).
- \`/tasks <acc_id>\`: show tasks assigned to the authorized Zalo account. \`/tasks\` remains a labeled overview for backward compatibility.
- Mini App Task selector: choose one Zalo cookie or Discord notifications. Old process-local tasks with missing account IDs appear under **Unassigned**, never silently attributed to another cookie.
- Legacy task snapshots now preserve account IDs and filter before applying the 100-row display limit, preventing one busy account from obscuring another.
- Multi-cookie execution retains its original engine and lifecycle. A per-cookie stop button is not shown for a shared task, because it would stop all participating accounts.

## Responsiveness and reliability changes

- User-visible \`.menu\`, \`.help\`, \`.dsbox\`, \`.tasks\` stay in an isolated interactive input/reply lane.
- Automatic group polling uses a bounded background queue (8 workers, 24 in-flight/queued slots) rather than borrowing command workers.
- Group version polling interval is throttled to >=1.5 seconds per account; rotating group polling to >=1 second, max 3 groups per batch, reducing avoidable request contention and Zalo rate-limit pressure under multiple cookies.
- No claim of 2× faster production command latency is made without before/after p50/p95 measurements on the real host.
- Zalo send exceptions now emit a sanitized class-only diagnostic (not cookies or message contents).

## Verification gates

- Python startup verifier.
- Full Python regression suite, including \`tests/test_v8_cookie_isolation.py\`.
- \`node --check static/control.js\`.
- Real Chromium local E2E using synthetic Telegram signed initData and browser fixtures; does not prove mobile WebView production compatibility.
- GitHub Actions per-commit SHA verification.
- Still blocked: authoritative DNS repair, production deployment SHA, Telegram Mini App live auth, Zalo cookies + Zalo provider access, task restart durability, real .menu response-time measurements, token rotation.

Do not merge the V8 stacked pull request until V6/V7 dependencies, credentials and production rollout requirements have been reviewed.