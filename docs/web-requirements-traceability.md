# Web production requirements traceability

| ID | Requirement | Implementation | Status | Evidence / limitation |
|---|---|---|---|---|
| WEB-01 | Web dashboard independent from Telegram bot | Web session principal; Render disables Telegram polling | VERIFIED | `tests/test_web_only_auth.py`, full suite |
| AUTH-01 | Protected dashboard and APIs | Password hash/session, rate limit, same-origin checks, production CSRF | VERIFIED | security and web-auth tests |
| SECRET-01 | No committed credentials | Environment-only sample and metadata-only secret scanner | VERIFIED | `scripts/check_secrets.py` |
| FB-01 | Facebook account connection | Official Facebook Login + Graph `/me`, encrypted token, revocation | IMPLEMENTED | mocked OAuth contract test; live credentials unavailable |
| FB-02 | Facebook cookie login / forced persistence | Not implemented | UNSUPPORTED | Private cookies cannot be kept alive after logout/revocation safely |
| DC-01 | Discord account connection | Official OAuth2 identify flow, optional PKCE, encryption, revocation | VERIFIED | `tests/test_oauth.py` |
| DC-02 | Discord personal user-token automation | Not implemented | UNSUPPORTED | Discord self-bot/user-token automation is not an authorized API |
| TASK-01 | Bounded concurrent task processing | Durable bounded queue and per-channel scheduling | VERIFIED | durable task tests and local benchmark |
| TASK-02 | Unified task visibility | Normalized durable + process-local task registry | VERIFIED | task registry/management tests |
| TASK-03 | Durable 90-second scheduler | Current watchdog uses accurate activity deadlines but remains process-local | PARTIAL | watcher tests; restart recovery is not implemented |
| STORE-01 | Persistence through Render restart | SQLite/WAL on `/var/data` Render disk | IMPLEMENTED | configuration verified; live Render restart test blocked |
| RT-01 | Realtime reconnect | Bounded SSE, heartbeat/stale detection and full resync | VERIFIED | browser and V6 recovery tests |
| UI-01 | Responsive premium dashboard | Existing compact mobile UI, states, toasts, gestures and reduced motion | VERIFIED | browser E2E at mobile widths |
| DEPLOY-01 | Render production deployment | Blueprint prepared | BLOCKED | workspace not confirmed; production secrets absent |
| DNS-01 | `tech-pak.store` DNS/TLS | No change made | BLOCKED | execution proxy rejected CONNECT; not proof of DNS failure |
