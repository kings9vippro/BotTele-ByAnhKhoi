# V14 web production audit — 2026-11-20

## Scope and architecture

The maintained runtime is a Flask web application (`app.py` → `glaze_app.py`) with a
server-rendered HTML shell, vanilla JavaScript control plane, SQLite/WAL persistence,
bounded notification workers, official OAuth identities, and process-local legacy Zalo
workers. `render.yaml` now declares web-only operation and a persistent Render disk.

| Area | Files inspected | Finding | Resolution / verification |
|---|---|---|---|
| Web authentication | `glaze_app.py`, `static/control.js`, `templates/miniapp.html` | A valid `/login` session still required Telegram environment variables; an empty seeded password could be accepted | Web sessions now have their own admin principal, empty passwords are rejected, production CSRF is enabled in Render; `tests/test_web_only_auth.py` |
| OAuth | `miniapp_oauth.py`, `official_integrations.py` | Discord OAuth was official and encrypted; Facebook callback was retired with legacy private routes | Added Facebook Login/Graph API adapter with state binding, encrypted tokens and revocation. Cookie login remains unsupported; `tests/test_oauth.py` |
| Task read model | `durable_tasks.py`, `task_registry.py`, `task_control.py`, `control_plane.py` | Durable webhook tasks and process-local Zalo tasks use distinct engines | Existing normalized registry retained; web principal can view/control legacy tasks without Telegram configuration; full regression suite |
| Storage | `app_storage.py`, `render.yaml` | SQLite uses WAL, but the Render Free filesystem was ephemeral | Render starter service now mounts `/var/data`; `APP_DATA_DIR` and `DATABASE_PATH` point to the disk |
| Frontend realtime | `static/control.js` | External-browser bootstrap stopped before trying a valid web cookie | Bootstrap now calls the session API first; 401/403/503 remain distinct and SSE retains bounded reconnect |
| Deployment | `app.py`, `gunicorn.conf.py`, `render.yaml` | Build validation ran before dependency installation; Telegram polling was configured by default | Install precedes verification; `DISABLE_TELEGRAM_BOT=1`; web health reports web mode |

## Supplied-file review

All supplied archives were path-checked before extraction into a temporary audit directory.
The three standalone Python files compile under Python 3.11. They were not executed and
were not copied into this repository.

| Input | Classification | Decision |
|---|---|---|
| `1-nuoifb.py` | Facebook browser-cookie/private endpoint automation | `UNSUPPORTED`; not integrated |
| `2-Qvulpmqtt-1-.py` | Messenger session/MQTT private endpoint automation | `UNSUPPORTED`; not integrated |
| `3-TooltreongonmesTrkhánh.py` | Bulk messaging with Facebook cookies and Discord user tokens | `UNSUPPORTED`; not integrated |
| `9app pro (1)-4.zip` | Mixed private API, OTP/bulk and spam-oriented scripts | `UNSUPPORTED` as a package; no code executed or copied |
| `botbylbachv21_1-1.zip` | Telegram UI mixed with Facebook-cookie and Discord-user-token automation | `UNSUPPORTED` as a package; no code executed or copied |

Only officially authorized Facebook Login/Graph API and Discord OAuth2/application
capabilities are exposed. A provider can revoke a token at any time; this system does not
claim credentials can remain alive after logout or revocation.

## Verification evidence

| Check | Result |
|---|---|
| `python scripts/verify_startup.py` | PASS |
| `python -m unittest discover -s tests -p 'test_*.py' -q` with non-secret fixture Telegram environment | PASS — 266 tests |
| `node --check static/control.js` | PASS |
| `node tests/control-browser.cjs` against local runtime | PASS |
| `python scripts/check_secrets.py` | PASS |
| Three supplied standalone files, `python -m py_compile` | PASS |

Queue benchmark (local simulated provider, 25 jobs, 5 channels, 40 ms service time):

- 1 worker: 1.070–1.147 s; median 1.083 s.
- 5 workers: 0.247–0.264 s; median 0.249 s.

This benchmark makes no third-party requests and is not a claim about provider delivery.

## Deployment and network status

- `tech-pak.store` could not be independently resolved from the execution sandbox.
- HTTPS requests were blocked by the sandbox egress proxy with `403 CONNECT tunnel
  failed`. This distinguishes an environment restriction from a proven production DNS or
  TLS failure; production DNS/HTTPS is therefore **BLOCKED / NOT VERIFIED**.
- The Render connector exposes one workspace named `My Workspace`, but no workspace has
  been selected or confirmed for deployment in this session. No deploy was triggered.
- Required production secrets remain operator-managed: `SECRET_KEY`, `ADMIN_PASS`,
  `OAUTH_ENCRYPTION_KEY`, plus official provider application credentials.

## Remaining risks

1. `glaze_app.py` still contains a large legacy Zalo implementation and retired Facebook /
   Discord user-token compatibility symbols. The HTTP boundary keeps private Facebook and
   Discord credential routes disabled, but a future extraction into isolated modules is
   advisable.
2. Zalo workers and the 90-second watcher are process-local. SQLite records task history,
   but these workers do not provide durable restart recovery or exactly-once execution.
3. A single Render web instance plus disk is the configured minimum. Horizontal scaling
   needs a distributed lease/queue before more than one instance may run schedulers safely.
4. Live Facebook/Discord OAuth requires real developer applications and approved redirect
   URIs. Local mocked provider tests are not a live authorization test.
