# V9: Telegram recovery, Zalo monitoring, and secret migration

## Critical production blocker: Mini App hostname

Both Google DNS and Cloudflare DNS returned NXDOMAIN for the **A** record of \`tech-pak.store\` during this audit. A page that cannot be resolved will show an empty/loading Telegram WebView *before any JavaScript executes*. Changing CSS cannot fix DNS. Verify domain registration, authoritative nameservers, A/CNAME records, HTTPS certificate, BotFather launch URL, service health and deployed Git SHA. Never invent a replacement URL.

## Telegram bot token — maintain the bot without publishing its credential

**The newest token is currently visible in the public GitHub history and the old \`main\` source.** Putting the token through Fernet after public exposure will not revoke it. Treat the token as potentially compromised; revoke/replace via BotFather as soon as practical. The automated patch does not revoke or overwrite an existing provider secret.

This branch removes the hardcoded fallback from source and adds two supported deployment methods:

### Option A (recommended): use hosting secret storage

1. Open the production hosting provider's service → Environment / Secrets.
2. Save \`TELEGRAM_BOT_TOKEN\` = the current token (privately; never paste it in GitHub, chat, PR, screenshot or logs).
3. Save \`TELEGRAM_ADMIN_ID\` = the authorized administrator's Telegram numeric ID.
4. Ensure a stable \`SECRET_KEY\` is present for Flask sessions.
5. Keep \`TELEGRAM_BOT_TOKEN_ENCRYPTED\` unset if using the direct secret variable.
6. Verify health, bot startup, and a signed Telegram Mini App launch **before merging a release**.

### Option B: optional Fernet ciphertext + separate key

1. Generate a Fernet key in a private local terminal and store it as a host secret \`TELEGRAM_BOT_TOKEN_KEY\`. Do not commit or send the key.
2. In a private environment only, configure \`TELEGRAM_BOT_TOKEN\` (existing token) and \`TELEGRAM_BOT_TOKEN_KEY\`, then run \`python scripts/encrypt_bot_token.py\`. The script prints only ciphertext.
3. Save that ciphertext as the host secret \`TELEGRAM_BOT_TOKEN_ENCRYPTED\`.
4. **Remove the direct \`TELEGRAM_BOT_TOKEN\` environment variable from that service after ciphertext and key have been verified**. Having both active is rejected to avoid ambiguity.
5. Keep the Fernet key and ciphertext in independently controlled secret locations where possible. Storing both as plain strings in the same public repository does **not** provide protection.

This is an *opt-in* feature: existing \`TELEGRAM_BOT_TOKEN\` host environment configurations keep working without changes. Code and logs never print plaintext values. Encryption has no effect until the owner configures the corresponding host secret.

## Telegram command repairs

- \`/tasks [acc_id]\`: readable line breaks, per-cookie filtering, explicit note when process-local tasks are empty after restart.
- \`/performance\`: human-readable workers, task state, API latency evidence, command handler p50/p95 with sample counts. This is not an end-to-end network delivery SLA.
- \`/send_multi\`: correct usage when the channel IDs or text are missing; provider rate limits stay enforced.
- \`/watch_status [acc_id]\`: live process snapshot by cookie and evidence of provider staleness; no message bodies in the status response.
- All slash commands share a reserved interactive lane, not the long-running background provider queue. No promise of zero latency or 2× speed without production measurement.

## Canh treo

- A watcher is keyed by **Zalo cookie account + group ID**, so two accounts that can see the same group cannot overwrite each other.
- New incoming messages are attributed to the correct cookie; ambiguous legacy stop callbacks are rejected instead of affecting another account.
- Group-history sync uses a bounded thread pool. Network latency cannot block the 90-second monitor clock.
- Reopening an existing watch preserves the original last-message timestamp.
- Per-cookie status exposes \`last_sync_at\` and \`last_sync_ok\` so older data are not falsely labeled "live".
- The Mini App renders the elapsed timer locally once a second and refetches the backend every 5s only on the visible Zalo page.
- Watch and legacy task state remain process-local; provider restarts and multiple Gunicorn processes can invalidate watches. Durable restart recovery is **not** claimed.

## Verification and rollout

Unit tests: \`python -m unittest discover -s tests -p 'test_*.py' -q\`.

Static checks: \`python scripts/verify_startup.py\`; \`python scripts/check_secrets.py\`; \`node --check static/control.js\`.

The change must be reviewed as a **draft PR until the owner confirms the actual hosting workspace and secure environment variable availability**. GitHub CI and local Chromium fixtures cannot verify DNS, real Telegram API delivery, Zalo cookie access, or production p50/p95.

No unsafe mass-sending optimization or third-party rate-limit bypass is introduced.