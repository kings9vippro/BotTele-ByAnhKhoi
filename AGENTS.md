# BotTele-ByAnhKhoi — persistent engineering rules

This file applies to **every Codex task** in this repository. Read the task first, then inspect only relevant files. Do not treat role names as evidence of real spawned agents.

## Project boundaries
- Python 3.11, Flask/Gunicorn, SQLite, Telegram bot, Zalo integration, Discord OAuth and Telegram Mini App (HTML/CSS/JavaScript).
- Key contracts: `control_plane.py`, `durable_tasks.py`, `task_control.py`, `miniapp_oauth.py`, `get_ck_im_zalo.py`, `glaze_app.py`, `static/`, `templates/`.
- Production deployment currently uses `render.yaml` and `Procfile`. Never assume a Vercel deployment exists.
- Read `docs/AI_AGENT_TEAM.md` when delegating, reviewing a patch or preparing a PR. Read `V4_DELIVERY.md` only when a change touches documented V4 behavior.

## Non-negotiable seven-role review — every code change
The main Codex thread is the orchestrator. Account for **all seven roles** before proposing a merge:
1. `scout`: changed-file ownership, dependency graph, blast radius.
2. `atlas`: architecture, schemas, API and backward compatibility.
3. `trace`: reproducible failure evidence, races, latency, logs.
4. `forge`: Python/Telegram/backend correctness and task execution.
5. `pixel`: Mini App UI, client state and responsive/accessibility behavior.
6. `echo`: tests, negative paths, regression and proof.
7. `shield`: authorization, credential safety, deployment and rollback risks.

For a code-changing task, ask independent subagents to review their areas **when the active runtime supports real spawning**. Cap simultaneous work at three subagents. Coordinate edits; only the designated implementation owner edits any one file at a time. Always wait for reports before final integration.

For a very small change or a runtime without spawn tools, still perform a brief seven-perspective gate review sequentially, recording `not impacted` with a reason where applicable. Clearly distinguish **actual subagent results** from **orchestrator-only reviews**; never invent agent IDs, parallel execution, model names, or test results.

## Engineering process
1. Restate the user's intent as acceptance criteria, including implied failure cases; do not silently add unrelated features.
2. Reproduce or baseline the defect before changing code, where feasible. Identify ownership and root cause; do not patch symptoms only.
3. Prefer the smallest safe change, preserve existing commands and frontend/backend contracts, and maintain owner isolation.
4. Verify Telegram -> API -> durable task state -> SSE/Mini App flows for cross-boundary changes. Browser/UI claims require actual evidence, not source inspection alone.
5. Use mocks/test credentials for external systems; do not send real Telegram, Zalo, or Discord messages in tests.
6. Record what was measured versus assumed. Performance work must include before/after measurements with the same workload.
7. Report limits and unknowns explicitly; never call an unrun test `passed`.

## Safety and review gates
- Never expose or commit bot tokens, OAuth secrets, session cookies, private keys, credentials or real-user data. Do not print credentials in error logs.
- Protect Telegram signed initData, per-owner authorization, CSRF/origin protections, SQLite transactional updates, retry idempotency, and task stop/pause semantics.
- Never automatically replay sends whose delivery status is unknown.
- Do not change deployment, secrets, production data, or merge to `main` without explicit user approval.
- Do not introduce credential collection, self-bot automation, token extraction or anti-abuse bypasses.
- Keep unrelated formatting/refactors out of bugfix PRs.

## Validation
Run relevant focused tests, then for substantive code changes:
```sh
python scripts/verify_startup.py
python -m unittest discover -s tests -p 'test_*.py' -q
```
If the installed browser/Node test tooling is available and UI changed, run `node tests/control-browser.cjs`. CI also runs the secret scanner and Gunicorn config check.

Before requesting merge, provide a seven-role review matrix (role, affected area, finding, evidence, verdict), files changed, commands and exact results, limitations, rollback plan and commit SHA. Use a feature branch and PR; do not auto-merge.
