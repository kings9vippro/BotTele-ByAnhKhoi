const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const calls = [];
  await page.route('**/api/miniapp/**', async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/miniapp/', '');
    calls.push(path);
    const data = {
      telemetry: { ok: true, live_accs: 1, running_tasks: 1, watched_boxes: 2, ram_mb: 85, tasks: [{ id: 'task-1', mode: 'test', target_label: 'nhóm', uptime_s: 10 }] },
      accounts: { ok: true, accounts: [{ id: 1, name: '<Account>', platform: 'zalo', uid: '123', chat_cmd_enabled: true }] },
      files: { ok: true, files: [{ filename: 'demo.txt', lines: 2, size_kb: 1 }], selected_nhay: 'demo.txt', selected_ngon: 'ngon.txt' },
      start_qr: { ok: true, session_id: 'session-1' },
      'qr_status/session-1': { ok: true, status: 'waiting_scan', message: 'Quét mã QR', qr_base64: 'data:image/png;base64,iVBORw0KGgo=' },
    }[path] || { ok: true, message: 'Đã cập nhật' };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
  page.on('dialog', dialog => dialog.accept());
  await page.goto('http://127.0.0.1:5873/miniapp', { waitUntil: 'domcontentloaded' });
  await page.getByText('85 MB').waitFor();
  assert.equal(await page.locator('html').evaluate(el => el.scrollWidth <= el.clientWidth), true);
  await page.screenshot({ path: '/tmp/glaze-miniapp-overview.png' });
  await page.getByRole('tab', { name: 'Tài khoản' }).click();
  await page.getByText('<Account>', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Tạo mã QR' }).click();
  await page.getByText('Quét mã QR', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Tắt lệnh' }).click();
  await page.getByRole('tab', { name: 'Tệp' }).click();
  await page.getByText('demo.txt', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Ngôn', exact: true }).click();
  await page.getByRole('tab', { name: 'Tác vụ' }).click();
  await page.getByRole('button', { name: 'Dừng', exact: true }).click();
  await page.getByRole('tab', { name: 'Lệnh' }).click();
  assert.equal(await page.getByText('.sticker', { exact: true }).count(), 1);
  assert.deepEqual(errors, []);
  for (const path of ['telemetry', 'accounts', 'start_qr', 'qr_status/session-1', 'toggle_acc_cmd', 'files', 'select_file', 'stop_task']) assert.ok(calls.includes(path), path);
  await browser.close();
  console.log('Mini App mobile navigation and mocked API flows passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
