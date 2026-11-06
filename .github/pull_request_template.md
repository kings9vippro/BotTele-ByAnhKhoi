## Goal and acceptance criteria

- What user behavior should change?
- How was the defect reproduced or baseline measured?

## Seven-role engineering gate

Describe **real spawned subagent** output, or explicitly write **orchestrator-only review**.
Do not mark unchecked work as passing.

| Role | Finding / impact or N/A reason | Evidence / test | Verdict (pass / block / not run) |
| --- | --- | --- | --- |
| Scout | | | |
| Atlas | | | |
| Trace | | | |
| Forge | | | |
| Pixel | | | |
| Echo | | | |
| Shield | | | |

## Validation

- [ ] Relevant focused test(s) recorded with exact commands and results
- [ ] `python scripts/verify_startup.py` (or explain why not run)
- [ ] `python -m unittest discover -s tests -p 'test_*.py' -q` (or explain why not run)
- [ ] UI/browser check if frontend changed (or marked not tested)
- [ ] Authz, secrets and owner data boundaries reviewed
- [ ] Regression and deployment impact documented
- [ ] Production credentials and real external sends excluded from tests

## Delivery

Files changed:

Unresolved risks / blocked tests:

Rollback:

Deployment needed? If yes, require separate user approval.
