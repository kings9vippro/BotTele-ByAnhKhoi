# V7 — Zalo 90-second monitoring and group browser

## Source migration
- The supplied \`zalo_group_checker.py\` is used as the functional specification.
- **Do not run the standalone script beside the Telegram bot.** The standalone script starts a second Zalo login/listener, writes plaintext cookies in local JSON, and can start unbounded monitor threads.
- The integrated \`zalo_group_checker.py\` is a safe, side-effect-free helper used by the existing \`CanhTreoWatchdogEngine\` and the authenticated Mini App routes. No cookies or secrets are added to Git.

## Behavior
- Default silence threshold: 90 seconds since the latest observed message; do not label group members who never sent observed messages as inactive.
- The original message timestamp is preserved after an alert. A new message resets the silence streak; no repeat alert for the same message.
- Group history polling rotates across all monitored boxes instead of always selecting only the first ten.
- Watch status is **process-local** and can be lost after a restart; do not report it as persisted state.
- Mini App exposes \`/api/miniapp/zalo_watch\` (GET, POST) and \`/api/miniapp/scan_boxes\` (POST). Existing Telegram auth middleware protects both.
- The explicit scan only uses an account already saved on the server. It is rate-limited to one scan per account per 30 seconds. API/group provider timeouts remain subject to network and account limits.
- Box listing uses the full group cache, paginated at 20 per page (up to 50). Selected IDs persist across pages with a max of five per launch.
- Mini App watches refresh while the Zalo page is visible; this is **not** a guarantee of uninterrupted real-time delivery in a sleeping Telegram WebView.
- The main bottom bar has five icon-only destinations. Existing screens are preserved through the tab list.

## Tests and deployment blockers
- Unit tests: \`python -m unittest discover -s tests -p 'test_*.py' -q\`.
- Syntax: \`python scripts/verify_startup.py\` and \`node --check static/control.js\`.
- Browser: \`NODE_PATH=... CHROMIUM_PATH=... node tests/control-browser.cjs\` against a local Flask fixture.
- Before merging to \`main\`, resolve the historic exposed Telegram token, deployment configuration, production domain/DNS, and test a real authorized Zalo account.
- No live Zalo login, permissioned group-history request, Telegram notification, or production task recovery was tested by this local suite.