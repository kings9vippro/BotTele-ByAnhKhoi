# GLAZE V11 - Compact Operations UI

## Design sources
Figma editable mockup: https://www.figma.com/design/SHSyEJrS6pnjqDm90IyrNv
Live reference inspected via Firecrawl: https://bot-anhkhoicute.onrender.com/miniapp
Screenshot supplied November 7, 2026.

## Changes
Premium compact dark style, single five-destination bottom bar, smaller status/metric/task cards, readable 14px typography and preserved eight functional sections via account/task shortcut buttons. V11 only adds v11.css and updates the existing template and control.js, retaining all form IDs and API contracts.

Direct Safari browser without Telegram initData now shows a dedicated recovery screen, rather than a nonfunctional dashboard. HTTP 401/403 and server authentication configuration errors also hide private pages. This does not bypass Telegram signature checking or admin authorization.

Account-scoped task registry skips an unrelated durable Discord notification query, while retaining role, account ID checks, and actual Zalo process-local task snapshots. Full multi-account dashboard sync is throttled to 60 seconds while foregrounded; task-specific refresh continues every 4 seconds when Tasks is selected and existing SSE remains.

## Limits
This reduces redundant work, not guarantees zero latency. Actual throughput depends on host CPU, concurrency, account providers and API rate limits. The existing queue already enforces per-owner fairness, bounded workers and backpressure; those safety limits were not removed.

Plaintext Telegram bot tokens must not be placed in public source. No Render Environment changes are included in V11. Existing runtime credentials must still be configured securely, or Telegram polling will not start.

## Acceptance
Python startup verification, full unittest suite, JavaScript syntax, mobile Chromium E2E with synthetic Telegram auth, and secret scanner. Live Telegram and Zalo account verification remain separate acceptance steps.

Figma sample values are design placeholders only. Production displays only API-authenticated data.