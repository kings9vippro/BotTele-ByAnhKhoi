# Development progress

## Completed

- Added Spotify Vietnam hot-hit catalog with ten official Spotify URLs and click-to-open embeds.
- Added Mini App account/box/task/music surfaces and accessible gesture-friendly navigation.
- Added owner-fair durable task claiming and regression coverage.
- Removed raw credential export and remote TOTP fallback.
- Sanitized user-facing exception responses.

## Remaining

- Encrypt existing Zalo credential columns with a deploy-managed key and migration/rollback procedure.
- Finish removal of legacy Facebook/Messenger compatibility storage after a data migration review.
- Verify OAuth and Zalo flows against staging accounts after deployment; tests deliberately do not use live credentials.

## Delivery status

The verified delivery was merged into `main` through PR #2 at merge commit
`cf6845edaa8cca0c30a60f49b6d0b124dbc35710`.  The source branch remains
`codex/v4-delivery`; this document is maintained on the default branch.
