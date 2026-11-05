# Verification report · V5

Run from the repository root with test-only environment variables:

```bash
TELEGRAM_BOT_TOKEN=test-token \
python -m unittest discover -s tests -p 'test_*.py' -q
python scripts/check_secrets.py
python scripts/verify_startup.py
node --check static/control.js
python -m py_compile app.py glaze_app.py control_plane.py durable_tasks.py
gunicorn --check-config app:app --config gunicorn.conf.py
git diff --check
```

Coordinator result: **126 tests passed** (`Ran 126 tests in 14.055s`). The suite
uses only fixture credentials and simulated providers. A run without the fixture
token is expected to fail the initData-signing test because production correctly
requires `TELEGRAM_BOT_TOKEN` from the environment.

Browser smoke (`node tests/control-browser.cjs`) passed against the local Flask
server, covering the eight tabs, account/box selection, task controls, theme and
gesture handling, Spotify catalog/embed shell, authentication and retired routes.
The local `/healthz` probe returned HTTP 200 with a minimal response. No Telegram
iPhone WebView or live Discord/Zalo/Spotify account was used.

The mocked notification benchmark ran 25 finite jobs across five channels with a
40 ms provider: one worker median **1.088 s**, five workers median **0.834 s** in
this run. This is a local bounded-concurrency signal, not a production latency or
zero-failure guarantee.

GitHub Actions `Python startup checks` for the delivery commit completed with
`success`. The post-merge squash tree matches the tested delivery tree. Render
live deployment/log verification remains blocked until a Render workspace is
selected.
