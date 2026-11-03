// Author: Dev Anh Khôi · Version: 1.2.0. Mocked API browser tests.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
let browser;

(async () => {
  browser = await chromium.launch({ executablePath: '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const calls = [];
  let selectedNgon = 'ngon.txt';
  let telemetryFailure = false;
  let providersFailure = false;
  await page.route('https://telegram.org/**', route => route.abort());
  await page.route('**/api/miniapp/**', async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/miniapp/', '');
    calls.push(path);
    if (path === 'select_file') selectedNgon = route.request().postDataJSON().filename;
    if (path === 'telemetry' && telemetryFailure) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ok: false, error: 'Lỗi lưu trữ mô phỏng'}) });
      return;
    }
    if (path === 'oauth/providers' && providersFailure) {
      await route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({ok: false, error: 'OAuth tạm không khả dụng'})});
      return;
    }
    const data = {
      telemetry: { ok: true, live_accs: 1, total_accs: 2, oauth_count: 1, listener_count: 1, account_platforms: {zalo: 1, discord: 1, messenger: 0, other: 0}, running_tasks: 1, watched_boxes: 2, ram_mb: 85, tasks: [{ id: 'task-1', mode: 'test', target_label: 'nhóm', uptime_s: 10 }] },
      accounts: { ok: true, accounts: [{ id: 1, name: '<Account>', platform: 'zalo', uid: '123', chat_cmd_enabled: true }] },
      files: { ok: true, files: [{ filename: 'demo.txt', lines: 2, size_kb: 1 }], selected_nhay: 'demo.txt', selected_ngon: selectedNgon },
      'oauth/providers': { ok: true, providers: [{id: 'discord', label: 'Discord', configured: true}, {id: 'facebook', label: 'Facebook', configured: false, missing: ['FACEBOOK_APP_ID']}] },
      'oauth/connections': { ok: true, connections: [{id: 1, provider: 'discord', provider_uid: '456', display_name: 'My Discord', status: 'authorized'}] },
      'oauth/start': { ok: true, url: 'https://bot.example/oauth/begin/example' },
      commands: {ok: true, commands: [{usage: '.menu', title: 'Mở bảng lệnh', description: 'Bảng lệnh chính', platforms: ['zalo', 'discord'], owner_only: false}, {usage: '.sticker', title: 'Tạo nhãn dán', description: 'Gửi ảnh của chính bạn', platforms: ['zalo'], owner_only: false}]},
      start_qr: { ok: true, session_id: 'session-1' },
      'qr_status/session-1': { ok: true, status: 'waiting_scan', message: 'Quét mã QR', qr_base64: 'data:image/png;base64,iVBORw0KGgo=' },
    }[path] || { ok: true, message: 'Đã cập nhật' };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
  page.on('dialog', dialog => dialog.accept());
  await page.goto('http://127.0.0.1:5873/miniapp', { waitUntil: 'domcontentloaded' });
  await page.getByText('85 MB').waitFor();
  await page.getByText('Phân tích tài khoản').waitFor();
  assert.equal(await page.locator('#platform-analytics .analytics-row').count(), 3);
  assert.equal(await page.locator('html').evaluate(el => el.scrollWidth <= el.clientWidth), true);
  await page.screenshot({ path: '/tmp/glaze-miniapp-overview.png' });
  await page.locator('#platform-analytics').scrollIntoViewIfNeeded();
  await page.screenshot({ path: '/tmp/glaze-miniapp-analytics.png' });
  await page.getByRole('tab', { name: 'Tài khoản' }).click();
  await page.getByText('<Account>', { exact: true }).waitFor();
  await page.getByText('My Discord', { exact: true }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Chưa cấu hình', exact: true }).isDisabled(), true);
  await page.getByRole('button', { name: 'Đăng nhập Discord' }).click();
  await page.getByRole('link', { name: 'Tiếp tục trên Discord' }).waitFor();
  await page.screenshot({ path: '/tmp/glaze-miniapp-accounts.png' });
  await page.getByRole('searchbox', { name: 'Tìm tài khoản' }).fill('missing');
  await page.getByText('Không tìm thấy tài khoản phù hợp.').waitFor();
  await page.getByRole('searchbox', { name: 'Tìm tài khoản' }).fill('Account');
  await page.getByText('<Account>', { exact: true }).waitFor();
  await page.getByLabel('Lọc nền tảng').selectOption('discord');
  await page.getByText('Không tìm thấy tài khoản phù hợp.').waitFor();
  await page.getByLabel('Lọc nền tảng').selectOption('all');
  await page.getByRole('button', { name: 'Tạo mã QR' }).click();
  await page.getByText('Quét mã QR', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Tắt lệnh' }).click();
  await page.getByRole('tab', { name: 'Tệp' }).click();
  await page.locator('#file-list').getByText('demo.txt', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Ngôn', exact: true }).click();
  await page.waitForFunction(() => document.getElementById('selected-ngon').textContent === 'demo.txt');
  await page.getByRole('tab', { name: 'Tác vụ' }).click();
  await page.getByRole('button', { name: 'Dừng', exact: true }).click();
  await page.getByRole('tab', { name: 'Lệnh' }).click();
  await page.getByText('.sticker', { exact: true }).waitFor();
  await page.getByRole('combobox', { name: 'Nền tảng lệnh' }).selectOption('discord');
  assert.equal(await page.getByText('.sticker', { exact: true }).count(), 0);
  await page.getByRole('combobox', { name: 'Nền tảng lệnh' }).selectOption('all');
  await page.getByRole('searchbox', { name: 'Tìm lệnh' }).fill('sticker');
  assert.equal(await page.locator('#command-list .command').count(), 1);
  await page.getByRole('tab', { name: 'Lệnh' }).press('Home');
  assert.equal(await page.getByRole('tab', { name: 'Tổng quan' }).getAttribute('aria-selected'), 'true');
  telemetryFailure = true;
  await page.getByRole('tab', { name: 'Tác vụ' }).click();
  await page.getByText('Dữ liệu cũ', { exact: true }).waitFor();
  assert.equal(await page.locator('#metric-accounts').textContent(), '1');
  assert.equal(await page.locator('#metric-memory').textContent(), '85 MB');
  assert.equal(await page.locator('#sync-error').textContent(), 'Lỗi lưu trữ mô phỏng');
  telemetryFailure = false;
  await page.getByRole('button', { name: 'Làm mới', exact: true }).click();
  await page.getByText('Đã đồng bộ', { exact: true }).waitFor();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.waitForFunction(() => document.querySelectorAll('.ripple').length === 0);
  await page.getByRole('tab', { name: 'Tài khoản' }).click();
  assert.equal(await page.locator('.ripple').count(), 0);
  for (const width of [320, 390, 768, 1280]) {
    await page.setViewportSize({width, height: 844});
    assert.equal(await page.locator('html').evaluate(el => el.scrollWidth <= el.clientWidth), true, `overflow at ${width}`);
  }
  providersFailure = true;
  await page.reload();
  await page.getByRole('tab', {name: 'Tài khoản'}).click();
  await page.locator('#account-list').getByText('<Account>', {exact: true}).waitFor();
  await page.getByText('OAuth tạm không khả dụng', {exact: true}).waitFor();
  assert.deepEqual(errors, []);
  for (const path of ['telemetry', 'accounts', 'oauth/providers', 'oauth/connections', 'oauth/start', 'commands', 'start_qr', 'qr_status/session-1', 'toggle_acc_cmd', 'files', 'select_file', 'stop_task']) assert.ok(calls.includes(path), path);
  await browser.close();
  console.log('Mini App mobile navigation and mocked API flows passed');
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => { if (browser) await browser.close(); });
