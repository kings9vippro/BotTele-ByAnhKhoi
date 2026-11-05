# Verification report

Run from the repository root with test-only environment variables:

```bash
DISABLE_TELEGRAM_BOT=1 DISABLE_BACKGROUND_WORKERS=1 \
TELEGRAM_BOT_TOKEN=test-token SECRET_KEY=test-only \
python -m unittest discover -s tests -p 'test_*.py' -q
python scripts/verify_startup.py
node --check static/control.js
git diff --check
```

Coordinator result: **114 tests passed** (`Ran 114 tests in 15.906s`).  Browser checks exercise Mini App tabs, account/box selection, task controls, theme/gesture handling, the Spotify catalog and official embed shell.  Live Discord, Zalo and Telegram credentials are intentionally not used in CI; provider behavior remains subject to their documented rate limits and availability.

The local benchmark uses mocked network calls only.  On 25 jobs across five channels with a 40ms mock API, one worker measured a 1.082s median and five workers 0.245s median.  It is a regression signal for worker isolation, not a claim of zero latency or unlimited concurrency.
