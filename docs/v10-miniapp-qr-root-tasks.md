# V10 — Mini App, QR session privacy, root tasks, typed files, fast commands

## Important: GitHub main is not the hosting environment

The previously configured tech-pak.store hostname still fails DNS resolution in this environment. Frontend CSS or passing GitHub Actions cannot fix missing DNS records or an offline hosting service. Before declaring success on iPhone:

1. Configure MINIAPP_PUBLIC_URL=https://your-working-https-host in the actual hosting service, or use the platform-provided RENDER_EXTERNAL_URL. The app uses the /miniapp path.
2. Verify /healthz and /miniapp both return HTTP 200 from a public network.
3. Use Telegram /miniapp_check to inspect the configured URL, and /miniapp to open it. Update BotFather's Menu Button or Mini App URL to the same HTTPS origin.
4. Previously stored Dark preferences are respected; choose Settings → Appearance → Light to switch. New visitors default to Light.
5. The hosting process must have TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID and stable SECRET_KEY in its secret environment. The V9 patch removed the plaintext fallback from source; historical Git commits still contain the previously exposed credential. Rotate via BotFather when appropriate.

## Zalo QR and owner-only private export

After successfully logging in with a QR scan, the bot saves the Zalo session under the Telegram user who initiated /qr, and replies in that chat with the account ID, UID and IMEI. In a Telegram one-to-one chat where chat ID equals the initiating user ID, a one-time button lets the user explicitly confirm revealing Cookie and IMEI within 120 seconds. The sensitive reply sets protect_content=true.

The raw cookie is never automatically sent into a group, never sent to the root administrator for someone else's session, and never logged or written into the public repository. Telegram's infrastructure still handles all messages and screenshots can expose credentials, so use only for accounts you control. The QR scanner and Telegram requester cannot automatically be proven to be the same human.

## Root task control

- Root user from TELEGRAM_ADMIN_ID can see all durable notification metadata and process-local Zalo tasks via /admin_tasks and the Mini App task registry.
- Root controls resolve the database owner by task ID, not by trusting client-supplied owner IDs.
- Ordinary users remain scoped to their own tasks.
- Legacy Zalo tasks and watch data are process-local. Restart may interrupt them; no durable recovery is claimed.

## Responsive Telegram, Zalo and Mini App UI

- /menu launches the interactive Telegram menu, /functions opens existing Zalo feature wizards; regular task/performance outputs are readable HTML cards.
- All in-chat Zalo dot, slash or bang commands now have an independent ten-worker executor. Short navigation uses a separate eight-worker executor. Provider rate limits remain in force; no 0-ms network delivery claim.
- Mini App defaults to a Light theme, but stores explicit preferences.
- /file_nhay and /file_ngon show separate compatible file inventories in Telegram. Mini App displays two distinct categories based on file metadata and independent selection slots.
- Mini App presents existing supported Treo ngôn, Treo nhây, typing, poll, photo and sticker backend modes.

## Verification

Run Python startup verification, all Python unittest discovery, JavaScript syntax checks and the Chromium mobile E2E test. Production URL, real QR login, provider messaging and remote hosting latency still need live checks after deployment.