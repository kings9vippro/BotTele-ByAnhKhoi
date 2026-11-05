# Security audit and release boundary

## Fixed in this delivery

- Removed the external TOTP fallback that transmitted a user-provided 2FA secret to a third-party host.  TOTP is now generated locally or rejected.
- Removed the Telegram callback that sent Zalo IMEI, cookies, `zpw_enk`, or Discord tokens.  The replacement returns redacted account status only.
- Removed the unapproved third-party Zalo credential fallback that sent an IMEI to an external endpoint and trusted its returned session key.
- Replaced raw exception reflection in Telegram and Mini App responses with stable, non-sensitive messages.
- Discord remains official OAuth2/webhook only; no self-bot or password collection was added.

## Operational requirements

- Rotate any Zalo session material that was previously exported by an older deployment.
- Keep `TELEGRAM_BOT_TOKEN`, OAuth secrets, `SECRET_KEY`, and database paths in the deployment secret store; never commit them.
- Use HTTPS for OAuth callbacks and Mini App hosting.

## Remaining review items

The repository still contains legacy compatibility code and plaintext-at-rest Zalo fields required by the current schema.  A production migration to encrypted columns needs a key-management decision and a rollback plan; it is not silently applied in this patch.  Legacy Facebook/Messenger compatibility symbols are guarded and not exposed through the V4 menu, but a separate migration is needed before deleting their shared storage.
