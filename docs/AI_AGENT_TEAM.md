# Seven-agent engineering playbook

This document defines a **persistent review process**, not seven always-on AI services.
Codex project-scoped custom agent definitions are in `.codex/agents/`; the main
Codex session acts as orchestrator. Models are deliberately **not pinned**:
the active signed-in account and parent session determine what is available.
All seven roles request `high` reasoning. Stronger levels can be selected
only if the chosen model and client support them.

## Roles and ownership

| Agent | Ownership | Example verification |
| --- | --- | --- |
| scout | Locate every affected path and owner | Route-handler / caller graph |
| atlas | Contracts, schema and architecture | Compatibility and migration plan |
| trace | Root cause, event ordering and latency | Repro, timing and logs |
| forge | Python server, Telegram bot and task engine | Focused Python tests |
| pixel | Mini App HTML/CSS/JS and UX | UI/browser contract tests |
| echo | Independent test strategy and regression | Command output and exit status |
| shield | Security, secrets and release safety | Threat scenarios / rollback |

## Every change: the seven-perspective gate

1. **Intake:** Orchestrator translates the request into testable acceptance
   criteria, including likely edge cases, but does not expand scope without reason.
2. **Independent discovery:** Spawn `scout`, `atlas` and `trace` when
   supported. They are read-only. Wait and reconcile conflicting findings.
3. **Scoped implementation:** Assign `forge` backend paths and `pixel`
   frontend paths. Non-overlapping edits may be parallel; otherwise serialize
   the work or let the orchestrator integrate the patch.
4. **Independent gates:** Spawn `echo` and `shield` when available. Both
   must report a verdict. Fix blockers, then repeat affected checks.
5. **Seven-role matrix:** Record a row for every role, even if the change
   does not affect its domain. `N/A` needs a concrete reason; `not run`
   is not `pass`. Include actual spawn evidence or mark `orchestrator review`.
6. **PR:** Show user-visible diff, measured outcomes, test command outputs,
   unresolved risks, rollback and deployment impact. No automatic merge.

This intentionally uses **at most three simultaneously active subagents**, not
seven competing writers. Seven viewpoints are mandatory for a proposed code
change; seven parallel model sessions are not. A backend-only change still
gets Pixel's compatibility/impact check and a UI-only change still gets
Forge's API-contract check. For a trivial one-line fix, the orchestrator may
perform the seven reviews itself and clearly label that limitation.

## Project-specific invariants
- Telegram handlers and the Mini App must use consistent owner permissions.
- Durable SQLite task IDs and state transitions are authoritative; UI state
  cannot be fabricated from optimistic local data.
- Unknown webhook send outcomes must not be automatically replayed.
- SQLite WAL does not make an ephemeral host's disk persistent.
- Test runs must never send live Telegram, Zalo or Discord messages.
- Cross-surface changes require Telegram -> API -> SQLite -> event/SSE -> UI checks.
- Existing `render.yaml` is the deployment source of truth. Vercel is optional,
  and must not be deployed or configured merely because its plugin is connected.

## Plugin responsibilities
- **GitHub:** source history, branches, tests, review and Pull Requests.
- **Firecrawl:** current public documentation, upstream issues, official API references.
- **Vercel:** deployment/build/runtime diagnostics only for a linked Vercel project.
- **OpenAI Platform:** optional API key setup for separately built agents;
  Codex Cloud does not require placing an API key in this repository.
- **Template Creator:** reusable artifact templates, not a Codex agent runtime.

Connector presence does **not** grant subagents automatic access in every Codex
surface. Check the actual parent session tools; do not fake integrations.

## Useful task prompt

```text
Use this repo's seven-agent engineering process.
First define acceptance criteria and ask Scout, Atlas and Trace for independent
read-only findings. Assign non-overlapping Forge/Pixel implementation only after
a root-cause plan. Have Echo and Shield review the final diff and tests.
Wait for all reports. Provide the seven-role matrix, exact evidence, CI results,
residual risks and rollback. Do not fake agent execution, auto-merge or deploy.
```

## Baseline verification

```sh
python scripts/check_secrets.py
python scripts/verify_startup.py
python -m unittest discover -s tests -p 'test_*.py' -q
# For UI changes, if test browser tooling is installed:
node tests/control-browser.cjs
```
CI in `.github/workflows/python-checks.yml` runs Python checks, unit tests
and Gunicorn configuration checks. The new agent-contract unit test validates
the *configuration files only*; it cannot prove agents were spawned.
