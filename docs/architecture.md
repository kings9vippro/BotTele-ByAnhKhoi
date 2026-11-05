# Glaze V4 architecture

## Runtime flow

Telegram commands and the Mini App call the same application services.  Durable task state is stored in SQLite and is claimed by bounded workers with owner-fair ordering.  Platform adapters keep Discord OAuth2/webhook flows separate from the existing Zalo session/listener path.

```text
Telegram Bot / Mini App
        -> auth + permission checks
        -> application services
        -> SQLite task/account state
        -> bounded task workers / listeners
        -> official Discord OAuth2 or Zalo adapter
```

## Concurrency boundaries

- Durable tasks are isolated by task id and owner; one failed task does not cancel unrelated work.
- Queue claims use owner-fair ordering and SQLite transactions.
- Existing Zalo listeners remain compatible with the legacy account schema.
- Artificial delay is configurable and defaults to zero; provider rate limits and `Retry-After` remain authoritative.
- The Render free instance keeps conservative worker pools; increasing thread counts without measurement is intentionally avoided.

## Mini App

The existing server-rendered Mini App keeps its stable Flask contract and adds a mobile-first control surface: account/box selection, task cards, live status, accessible tabs, glass navigation, reduced-motion support, and an on-demand Spotify catalog.  Spotify playback is only opened through official HTTPS embeds after a user click; no audio is proxied by the server.

## Security boundaries

Discord is OAuth2 only.  Discord passwords and user tokens are never accepted.  Zalo session material stays server-side and is not exported through Telegram callbacks or API responses.  Mini App authentication must pass the server-side Telegram `initData` validator before protected state is returned.
