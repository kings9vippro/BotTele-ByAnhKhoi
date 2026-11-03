/* GLAZE · Author: Dev Anh Khôi · Version: 1.3.0 */
'use strict';

(() => {
  let tg = window.Telegram?.WebApp;
  // Telegram includes signed launch data in the fragment. The backend still
  // validates its HMAC and owner; the UI need not wait for the external SDK.
  const launchData = new URLSearchParams(location.hash.slice(1)).get('tgWebAppData') || '';
  function initializeTelegram() {
    tg = window.Telegram?.WebApp;
    if (tg) { tg.ready(); tg.expand(); }
  }
  initializeTelegram();
  document.getElementById('telegram-sdk')?.addEventListener('load', initializeTelegram, {once: true});
  const $ = id => document.getElementById(id);
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const pending = new Map();
  let currentTab = 'overview';
  let toastTimer;
  let qrTimer;
  let qrGeneration = 0;
  let accounts = [];
  let files = [];
  let commands = [];
  let selected = {};
  let lastSuccess;
  let telemetryCache;
  let providerView = null;
  let integrationView = null;

  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = String(text);
    if (className) element.className = className;
    return element;
  }

  function toast(message) {
    $('toast').textContent = message;
    $('toast').classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => $('toast').classList.remove('show'), 4000);
  }

  function showError(error) {
    $('sync-error').textContent = error.message || 'Không thể cập nhật. Hãy thử Đồng bộ.';
    $('sync-error').hidden = false;
    $('connection').classList.remove('online');
    $('connection-label').textContent = lastSuccess ? 'Dữ liệu cũ' : 'Chưa kết nối';
  }

  function fire(promise) { promise.catch(showError); }

  async function allUpdates(operations) {
    // Report partial failure only after all renderers finish. Otherwise a later
    // successful telemetry render can erase an earlier account/OAuth error.
    const results = await Promise.allSettled(operations);
    const failed = results.find(result => result.status === 'rejected');
    if (failed) throw failed.reason;
    return results.map(result => result.value);
  }

  async function once(key, operation, fresh = false) {
    if (fresh && pending.has(key)) {
      try { await pending.get(key); } catch (_) { /* A mutation needs a new read even if the old read failed. */ }
    }
    if (pending.has(key)) return pending.get(key);
    const promise = operation();
    pending.set(key, promise);
    try { return await promise; } finally { pending.delete(key); }
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (tg?.initData || launchData) headers.set('X-Telegram-Init-Data', tg?.initData || launchData);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), options.timeout || 15000);
    const { timeout: _, ...fetchOptions } = options;
    try {
      const response = await fetch('/api/miniapp/' + path, {
        ...fetchOptions, headers, signal: controller.signal, credentials: 'same-origin', cache: 'no-store'
      });
      let data;
      try { data = await response.json(); } catch (_) { throw new Error('Máy chủ không trả dữ liệu hợp lệ. Hãy thử Đồng bộ.'); }
      if (!response.ok || data.ok === false) throw new Error(data.error || data.message || 'Không thể thực hiện yêu cầu');
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Máy chủ chưa trả lời kịp. Hãy Đồng bộ để kiểm tra kết quả trước khi gửi lại.');
      throw error;
    } finally { clearTimeout(timeout); }
  }

  function post(path, data, timeout) {
    return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data), timeout });
  }

  async function busy(button, operation) {
    if (button.disabled) return;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    try { await operation(); } catch (error) { toast(error.message || 'Không thể kết nối'); showError(error); }
    finally { button.disabled = false; button.removeAttribute('aria-busy'); }
  }

  function action(label, handler, className = 'button small') {
    const button = node('button', label, className);
    button.type = 'button';
    button.addEventListener('click', () => busy(button, handler));
    return button;
  }

  function empty(target, text) { target.replaceChildren(node('div', text, 'empty')); }

  function row(title, detail) {
    const item = node('div', undefined, 'row');
    const main = node('div', undefined, 'row-main');
    main.append(node('div', title, 'row-title'), node('div', detail, 'row-meta'));
    item.append(main);
    return item;
  }

  const pages = {
    overview: ['Không gian quản lý của bạn.', 'Tài khoản, dữ liệu và công cụ. Gọn trong một không gian.'],
    tasks: ['Theo dõi. Chủ động.', 'Kiểm tra và dừng các tác vụ trong hệ thống.'],
    accounts: ['Kết nối của bạn.', 'Ba nền tảng. Một nơi quản lý. Trạng thái rõ ràng.'],
    files: ['Kho tệp. Gọn gàng.', 'Tệp của bạn, lựa chọn của bạn — được lưu và đồng bộ.'],
    commands: ['Lệnh nào cũng rõ.', 'Tra cứu cú pháp, nền tảng và quyền trước khi sử dụng.']
  };

  function loadCurrent() {
    if (currentTab === 'accounts') return allUpdates([loadAccounts(), refresh()]);
    if (currentTab === 'files') return loadFiles();
    if (currentTab === 'commands') return loadCommands();
    return refresh();
  }

  function switchTab(name) {
    if (!pages[name]) return;
    currentTab = name;
    document.querySelector('.nav').style.setProperty('--tab-index', String(tabs.findIndex(tab => tab.dataset.tab === name)));
    document.querySelectorAll('[data-tab]').forEach(button => {
      const active = button.dataset.tab === name;
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll('.pane').forEach(panel => { panel.hidden = panel.id !== name; });
    $('page-title').textContent = pages[name][0];
    $('page-description').textContent = pages[name][1];
    window.scrollTo({ top: 0, behavior: 'instant' });
    if (tg?.HapticFeedback && !reducedMotion.matches) tg.HapticFeedback.selectionChanged();
    fire(loadCurrent());
  }

  const tabs = [...document.querySelectorAll('[data-tab]')];
  tabs.forEach((button, index) => {
    button.addEventListener('click', () => switchTab(button.dataset.tab));
    button.addEventListener('keydown', event => {
      const next = { ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1 }[event.key];
      if (next === undefined) return;
      event.preventDefault();
      tabs[next].focus();
      switchTab(tabs[next].dataset.tab);
    });
  });
  document.querySelectorAll('[data-go]').forEach(button => button.addEventListener('click', () => switchTab(button.dataset.go)));

  function renderTasks(target, tasks) {
    if (!tasks.length) return empty(target, 'Chưa có tác vụ nào đang chạy.');
    target.replaceChildren();
    tasks.forEach(task => {
      const labels = {running: 'Đang chạy', stopping: 'Đang dừng', stopped: 'Đã dừng', interrupted: 'Bị ngắt khi khởi động lại', finished: 'Đã kết thúc', completed: 'Hoàn tất', failed: 'Lỗi'};
      const state = task.status || 'running';
      const item = row(task.name || task.mode || 'Tác vụ', `${task.mode || 'task'} · ${task.target_label || '—'} · ${(task.account_names || []).join(', ') || 'Chưa có tên tài khoản'} · ${labels[state] || state} · ${task.uptime_s || 0} giây · Đã gửi ${task.sent || 0} / Lỗi ${task.failed || 0}`);
      item.append(node('div', '#' + task.id, 'row-meta task-id'));
      if (task.can_stop !== false && state !== 'stopped') {
        const stopButton = action(state === 'stopping' ? 'Đang dừng…' : 'Dừng', async () => {
        const result = await post('stop_task', { task_id: task.id });
        toast(result.message || 'Đã gửi yêu cầu dừng');
        await refresh(true);
        }, 'button small danger');
        stopButton.disabled = state === 'stopping';
        item.append(stopButton);
      }
      target.append(item);
    });
  }

  function renderTelemetry(data) {
    telemetryCache = data;
    $('metric-accounts').textContent = data.total_accs ?? '—';
    $('metric-account-total').textContent = 'Đang bật: ' + (data.live_accs ?? '—');
    $('metric-tasks').textContent = data.running_tasks ?? '—';
    $('metric-listeners').textContent = 'Luồng lắng nghe: ' + (data.listener_count ?? '—');
    $('metric-oauth').textContent = (data.oauth_count || 0) + (data.official_count || 0);
    $('metric-memory').textContent = data.ram_mb === undefined ? '—' : data.ram_mb + ' MB';
    const visibleTasks = $('task-filter').value === 'all' ? (data.tasks || []) : (data.tasks || []).filter(task => ['running', 'stopping'].includes(task.status || 'running'));
    renderTasks($('overview-tasks'), (data.tasks || []).filter(task => ['running', 'stopping'].includes(task.status || 'running')).slice(0, 3));
    renderTasks($('task-list'), visibleTasks);
    $('storage-info').textContent = `Kho dữ liệu: ${(data.storage_id || 'chưa xác định').slice(0, 12)} · Bản ${data.version || '—'} · ${data.total_accs ?? '—'} tài khoản`;
    const target = $('platform-analytics');
    target.replaceChildren();
    if (data.account_platforms) {
      for (const [key, label] of [['zalo', 'Zalo'], ['discord', 'Discord'], ['messenger', 'Messenger'], ['other', 'Khác']]) {
        const count = Math.max(0, Number(data.account_platforms[key]) || 0);
        if (key === 'other' && !count) continue;
        const line = node('div', undefined, 'analytics-row');
        const track = node('div', undefined, 'bar-track');
        track.setAttribute('aria-hidden', 'true');
        const fill = node('div', undefined, 'bar-fill');
        fill.style.width = (data.total_accs ? Math.min(100, count / data.total_accs * 100) : 0) + '%';
        track.append(fill);
        line.append(node('span', label), track, node('strong', count));
        target.append(line);
      }
      target.append(node('p', 'Bản ghi đã lưu cho bot, không phải trạng thái đăng nhập. Liên kết OAuth được thống kê riêng.', 'analytics-note'));
    } else empty(target, 'Chưa có dữ liệu phân tích.');
    lastSuccess = new Date(data.snapshot_at ? data.snapshot_at * 1000 : Date.now());
    $('last-updated').textContent = 'Đồng bộ thành công lúc ' + lastSuccess.toLocaleTimeString('vi-VN');
    $('connection').classList.add('online');
    $('connection-label').textContent = 'Đã đồng bộ';
    $('sync-error').hidden = true;
  }

  function refresh(fresh = false) { return once('telemetry', async () => renderTelemetry(await api('telemetry')), fresh); }

  async function syncAll() {
    return once('sync', async () => {
      renderTelemetry(await post('sync', {}));
      await allUpdates([loadAccounts(true), loadFiles(true), loadCommands()]);
      toast('Đã đồng bộ tài khoản, tệp và bảng lệnh');
    });
  }
  document.querySelectorAll('[data-sync]').forEach(button => button.addEventListener('click', () => busy(button, syncAll)));
  document.querySelectorAll('[data-refresh]').forEach(button => button.addEventListener('click', () => busy(button, refresh)));
  $('stop-all').addEventListener('click', event => busy(event.currentTarget, async () => {
    if (!confirm('Dừng tất cả tác vụ đang chạy?')) return;
    const result = await post('quick_action', { action: 'stop_all' });
    toast(result.message || 'Đã dừng');
    await refresh(true);
  }));

  function renderAccounts() {
    const query = $('account-search').value.trim().toLocaleLowerCase();
    const filter = $('account-filter').value;
    const items = accounts.filter(account => (filter === 'all' || (account.platform || 'zalo').toLowerCase() === filter) && [account.name, account.uid, account.id].some(value => String(value ?? '').toLocaleLowerCase().includes(query)));
    $('account-count').textContent = `Hiển thị ${items.length} / ${accounts.length} tài khoản đã lưu`;
    const target = $('account-list');
    if (!items.length) return empty(target, accounts.length ? 'Không tìm thấy tài khoản phù hợp.' : 'Chưa có tài khoản chạy bot trong dữ liệu.');
    target.replaceChildren();
    items.forEach(account => {
      const status = account.listener_started ? 'Luồng đã khởi chạy' : 'Chưa có luồng lắng nghe';
      const item = row(account.name || `Tài khoản #${account.id}`, `${(account.platform || 'zalo').toUpperCase()} · #${account.id} · ${account.uid || 'Chưa có UID'} · Đã lưu · ${status}`);
      const controls = node('div', undefined, 'actions');
      controls.append(action(account.chat_cmd_enabled ? 'Tắt lệnh' : 'Bật lệnh', async () => {
        const result = await post('toggle_acc_cmd', { acc_id: account.id });
        toast(result.message || 'Đã cập nhật');
        await allUpdates([loadAccounts(true), refresh(true)]);
      }), action('Xóa', async () => {
        if (!confirm(`Xóa tài khoản ${account.name || account.id} khỏi bot?`)) return;
        const result = await post('delete_acc', { acc_id: account.id });
        toast(result.message || 'Đã xóa');
        await allUpdates([loadAccounts(true), refresh(true)]);
      }, 'button small danger'));
      item.append(controls);
      target.append(item);
    });
  }

  function renderProviders(providers) {
    const view = JSON.stringify(providers);
    if (view === providerView) return;
    providerView = view;
    $('oauth-providers').replaceChildren();
    providers.forEach(provider => {
      const card = node('article', undefined, 'card provider ' + provider.id);
      const heading = node('div', undefined, 'provider-name');
      heading.append(node('span', provider.id === 'discord' ? 'D' : 'f', 'provider-icon'), node('span', provider.label));
      card.append(heading, node('p', provider.configured ? 'Trang ủy quyền chính thức' : 'Chưa cấu hình ứng dụng'));
      if (!provider.configured) {
        const details = node('details');
        const list = node('ul', undefined, 'config-list');
        (provider.missing || []).forEach(key => list.append(node('li', key)));
        details.append(node('summary', 'Cấu hình còn thiếu'), list);
        card.append(details);
      }
      const button = action(provider.configured ? 'Đăng nhập ' + provider.label + ' →' : 'Chưa cấu hình', async () => {
        const result = await post('oauth/start', { provider: provider.id });
        const url = new URL(result.url);
        if (url.protocol !== 'https:' || !url.pathname.startsWith('/oauth/begin/')) throw new Error('Đường dẫn OAuth không hợp lệ');
        $('oauth-link').href = url.href;
        $('oauth-link').textContent = 'Tiếp tục trên ' + provider.label + ' →';
        $('oauth-link').hidden = false;
        if (tg?.openLink) tg.openLink(url.href);
        else toast('Bấm Tiếp tục để mở trang đăng nhập chính thức');
      }, 'button');
      button.disabled = !provider.configured;
      card.append(button);
      const setup = node('details');
      setup.append(node('summary', 'Cấu hình ứng dụng'));
      const fields = [['client_id', 'App / Client ID'], ['client_secret', 'App / Client Secret', 'password'], ['public_base_url', 'URL HTTPS của bot', 'url']];
      if (provider.id === 'facebook') fields.push(['graph_version', 'Phiên bản Graph API (vN.N)']);
      setup.append(configurationForm(fields, async values => {
        const result = await post('oauth/configure', {provider: provider.id, ...values});
        $('configuration-result').textContent = result.message + ' Callback: ' + result.redirect_uri;
        $('configuration-result').hidden = false;
        await loadAccounts(true);
      }));
      card.append(setup);
      $('oauth-providers').append(card);
    });
  }

  function renderConnections(connections) {
    const target = $('oauth-connections');
    if (!connections.length) return empty(target, 'Chưa có liên kết OAuth. Kết nối ở phía trên để bắt đầu.');
    target.replaceChildren();
    connections.forEach(connection => {
      const label = connection.provider === 'discord' ? 'Discord' : 'Facebook';
      const state = connection.status === 'authorized' ? 'Quyền OAuth chưa hết hạn' : 'Cần kết nối lại';
      const item = row(connection.display_name, `${label} · ${connection.provider_uid} · ${state}`);
      item.append(action('Gỡ liên kết', async () => {
        if (!confirm(`Xóa liên kết ${label} đã lưu tại bot?`)) return;
        const result = await post('oauth/disconnect', { id: connection.id });
        toast(result.message);
        await allUpdates([loadAccounts(true), refresh(true)]);
      }, 'button small danger'));
      target.append(item);
    });
  }

  function loadAccounts(fresh = false) {
    return once('accounts', async () => {
      // A failed provider service must not hide successfully stored Zalo accounts.
      const results = await Promise.allSettled([api('accounts'), api('oauth/providers'), api('oauth/connections'), api('integrations')]);
      if (results[0].status === 'fulfilled') {
        accounts = results[0].value.accounts || [];
        renderAccounts();
      }
      if (results[1].status === 'fulfilled') renderProviders(results[1].value.providers || []);
      else if (!$('oauth-providers').querySelector('.provider')) empty($('oauth-providers'), 'Chưa tải được cấu hình OAuth. Hãy Đồng bộ lại.');
      if (results[2].status === 'fulfilled') renderConnections(results[2].value.connections || []);
      if (results[3].status === 'fulfilled') renderOfficialIntegrations(results[3].value.integrations || []);
      const failure = results.find(result => result.status === 'rejected');
      if (failure) throw failure.reason;
    }, fresh);
  }
  $('account-search').addEventListener('input', renderAccounts);
  function configurationForm(fields, submit) {
    const form = node('form', undefined, 'stack details-body');
    for (const [name, title, type = 'text'] of fields) {
      const label = node('label', title, 'field');
      const input = node('input');
      input.name = name;
      input.type = type;
      input.required = true;
      input.autocomplete = type === 'password' ? 'new-password' : 'off';
      if (name === 'public_base_url' && location.protocol === 'https:') input.value = location.origin;
      label.append(input);
      form.append(label);
    }
    const button = node('button', 'Xác minh và lưu cấu hình', 'button full');
    button.type = 'submit';
    form.append(button);
    form.addEventListener('submit', event => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(form));
      busy(button, async () => { await submit(values); form.reset(); });
    });
    return form;
  }

  function renderOfficialIntegrations(integrations) {
    const view = JSON.stringify(integrations);
    if (view === integrationView) return;
    integrationView = view;
    $('official-integrations').replaceChildren();
    for (const provider of ['discord', 'facebook']) {
      const states = integrations.filter(item => item.provider === provider && (item.configured || item.id));
      const title = provider === 'discord' ? 'Discord Bot' : 'Facebook Page';
      const setupCard = node('article', undefined, 'card stack');
      setupCard.append(node('h3', title), node('p', states.length + ' kết nối đã lưu'));
      const details = node('details');
      details.append(node('summary', 'Thêm hoặc cập nhật ' + title));
      const fields = [['token', provider === 'discord' ? 'Bot Token (Discord Developer Portal)' : 'Page Access Token', 'password'], ['owner_ids', provider === 'discord' ? 'Discord User ID quản lý toàn hệ thống (phân cách dấu phẩy)' : 'PSID quản lý toàn hệ thống (phân cách dấu phẩy)']];
      if (provider === 'discord') fields.push(['public_key', 'Application Public Key']);
      else fields.push(['page_id', 'Page ID'], ['app_secret', 'Meta App Secret', 'password'], ['verify_token', 'Webhook Verify Token', 'password'], ['graph_version', 'Phiên bản Graph API (vN.N)']);
      details.append(configurationForm(fields, async values => {
        const result = await post('integrations/configure', {provider, ...values}, 25000);
        $('configuration-result').textContent = result.message + ' Callback: ' + location.origin + result.callback_path;
        $('configuration-result').hidden = false;
        await allUpdates([loadAccounts(true), refresh(true)]);
      }));
      setupCard.append(details);
      $('official-integrations').append(setupCard);
      for (const state of states) {
        const card = node('article', undefined, 'card stack');
        card.append(node('h3', state.name || title + ' #' + state.id), node('p', 'ID ' + state.id + ' · ' + (state.configured ? 'Đã lưu cấu hình' : state.error || 'Cần cấu hình lại')));
        card.append(node('p', 'Callback HTTPS: ' + location.origin + (state.callback_path || '/integrations/' + provider + '/' + state.id)));
        if (provider === 'discord' && state.configured) card.append(action('Đăng ký 4 lệnh Discord', async () => {
          const result = await post('integrations/discord/commands', {id: state.id}, 60000);
          toast(result.message);
        }, 'button'));
        card.append(action('Xóa cấu hình ' + title, async () => {
          if (!confirm('Xóa cấu hình ' + (state.name || title) + ' #' + state.id + ' lưu tại bot?')) return;
          const result = await post('integrations/disconnect', {provider, id: state.id});
          toast(result.message);
          await allUpdates([loadAccounts(true), refresh(true)]);
        }, 'button small danger'));
        $('official-integrations').append(card);
      }
    }
  }

  $('task-filter').addEventListener('change', () => {
    const tasks = telemetryCache?.tasks || [];
    renderTasks($('task-list'), $('task-filter').value === 'all' ? tasks : tasks.filter(task => ['running', 'stopping'].includes(task.status || 'running')));
  });
  $('compare-storage').addEventListener('click', event => busy(event.currentTarget, async () => {
    const expected = $('receipt-storage').value.trim().toLowerCase();
    if (!/^[a-f0-9]{12,32}$/.test(expected)) throw new Error('Nhập mã kho trong xác nhận Telegram, không nhập cookie hoặc token');
    await allUpdates([refresh(true), loadAccounts(true)]);
    const actual = telemetryCache?.storage_id || '';
    $('storage-result').textContent = actual.startsWith(expected)
      ? `Cùng kho dữ liệu. Máy chủ hiện có ${telemetryCache.total_accs} tài khoản. Nếu số lượng không đúng, cần kiểm tra lần khởi động lại và lưu trữ của dịch vụ.`
      : 'Hai mã kho khác nhau. Mini App đang đọc dữ liệu khác với xác nhận Telegram; kiểm tra URL dịch vụ và cấu hình DATABASE_PATH / APP_DATA_DIR.';
  }));
  $('account-filter').addEventListener('change', renderAccounts);
  $('refresh-accounts').addEventListener('click', event => busy(event.currentTarget, async () => {
    await allUpdates([loadAccounts(true), refresh(true)]);
    toast('Đã đọc lại tài khoản từ dữ liệu');
  }));
  $('add-account').addEventListener('click', event => busy(event.currentTarget, async () => {
    const raw = $('cookie-input').value.trim();
    if (!raw) throw new Error('Hãy nhập Cookie + IMEI của bạn');
    const result = await post('add_cookie', { raw_input: raw }, 45000);
    $('cookie-input').value = '';
    toast(result.message || 'Đã lưu tài khoản');
    await allUpdates([loadAccounts(true), refresh(true)]);
  }));

  $('start-qr').addEventListener('click', event => busy(event.currentTarget, async () => {
    clearTimeout(qrTimer);
    const generation = ++qrGeneration;
    $('qr-area').hidden = false;
    $('qr-image').hidden = true;
    $('qr-message').textContent = 'Đang tạo mã QR…';
    const result = await post('start_qr', {});
    if (!result.session_id) throw new Error('Không tạo được mã QR');
    const deadline = Date.now() + 180000;
    async function poll() {
      if (generation !== qrGeneration) return;
      if (Date.now() > deadline) { $('qr-message').textContent = 'Mã QR đã hết thời gian chờ. Hãy tạo lại.'; return; }
      try {
        const data = await api('qr_status/' + encodeURIComponent(result.session_id));
        if (generation !== qrGeneration) return;
        $('qr-message').textContent = data.message || 'Quét mã bằng ứng dụng Zalo';
        if (data.qr_base64) {
          $('qr-image').src = data.qr_base64.startsWith('data:image/') ? data.qr_base64 : 'data:image/png;base64,' + data.qr_base64;
          $('qr-image').hidden = false;
        }
        if (data.status === 'success') {
          toast('Đã lưu tài khoản từ QR');
          await allUpdates([loadAccounts(true), refresh(true)]);
          return;
        }
        if (['expired', 'error', 'failed', 'declined'].includes(data.status)) return;
        qrTimer = setTimeout(poll, document.hidden ? 7000 : 2000);
      } catch (error) { $('qr-message').textContent = error.message + ' Hãy tạo lại QR nếu cần.'; }
    }
    await poll();
  }));

  function renderFiles() {
    $('selected-nhay').textContent = selected.nhay || '—';
    $('selected-ngon').textContent = selected.ngon || '—';
    const query = $('file-search').value.trim().toLocaleLowerCase();
    const items = files.filter(file => file.filename.toLocaleLowerCase().includes(query));
    const target = $('file-list');
    if (!items.length) return empty(target, files.length ? 'Không tìm thấy tệp phù hợp.' : 'Kho tệp đang trống.');
    target.replaceChildren();
    items.forEach(file => {
      const kinds = ['nhay', 'ngon'].filter(kind => selected[kind] === file.filename);
      const item = row(file.filename, `${file.lines || 0} dòng · ${file.size_kb || 0} KB${kinds.length ? ' · Đang chọn: ' + kinds.join(', ') : ''}`);
      const controls = node('div', undefined, 'actions');
      for (const kind of ['nhay', 'ngon']) {
        const button = action(kind === 'nhay' ? 'Nhây' : 'Ngôn', async () => {
          const result = await post('select_file', { filename: file.filename, target: kind });
          toast(result.message || 'Đã lưu lựa chọn');
          await loadFiles(true);
        });
        button.setAttribute('aria-pressed', String(selected[kind] === file.filename));
        controls.append(button);
      }
      controls.append(action('Xóa', async () => {
        if (!confirm(`Xóa tệp ${file.filename}?`)) return;
        const result = await post('delete_file', { filename: file.filename });
        toast(result.message || 'Đã xóa');
        await loadFiles(true);
      }, 'button small danger'));
      item.append(controls);
      target.append(item);
    });
  }

  function loadFiles(fresh = false) {
    return once('files', async () => {
      const data = await api('files');
      files = data.files || [];
      selected = { nhay: data.selected_nhay, ngon: data.selected_ngon };
      renderFiles();
    }, fresh);
  }
  $('file-search').addEventListener('input', renderFiles);
  $('refresh-files').addEventListener('click', event => busy(event.currentTarget, loadFiles));
  $('file-upload').addEventListener('change', event => busy(event.currentTarget, async () => {
    const input = event.target;
    const file = input.files[0];
    if (!file) return;
    try {
      if (file.size > 1024 * 1024) throw new Error('Tệp vượt giới hạn 1 MB');
      const form = new FormData();
      form.append('file', file);
      form.append('target', $('file-target').value);
      const data = await api('upload_file', { method: 'POST', body: form });
      toast(data.message || 'Đã tải và chọn tệp');
      await loadFiles(true);
    } finally { input.value = ''; }
  }));
  $('save-file').addEventListener('click', event => busy(event.currentTarget, async () => {
    const filename = $('file-name').value.trim();
    const content = $('file-content').value;
    if (!filename || !content.trim()) throw new Error('Hãy nhập tên và nội dung tệp');
    const data = await post('add_file', { filename, content, target: $('file-target').value });
    $('file-name').value = '';
    $('file-content').value = '';
    toast(data.message || 'Đã lưu và chọn tệp');
    await loadFiles(true);
  }));

  function renderCommands() {
    const query = $('command-search').value.trim().toLocaleLowerCase();
    const platform = $('command-platform').value;
    const items = commands.filter(command => (platform === 'all' || command.platforms.includes(platform)) && [command.usage, command.title, command.description].some(value => value.toLocaleLowerCase().includes(query)));
    const target = $('command-list');
    if (!items.length) return empty(target, 'Không có lệnh phù hợp.');
    target.replaceChildren();
    items.forEach(command => {
      const button = action('', async () => {
        try { await navigator.clipboard.writeText(command.usage); toast('Đã sao chép ' + command.usage); }
        catch (_) { toast('Lệnh: ' + command.usage); }
      }, 'button command');
      const tags = node('div', undefined, 'actions');
      command.platforms.forEach(platform => tags.append(node('span', platform.toUpperCase(), 'badge')));
      if (command.owner_only) tags.append(node('span', 'CHỦ TÀI KHOẢN', 'badge pink-badge'));
      button.append(node('code', command.usage), node('strong', command.title), node('small', command.description), tags);
      target.append(button);
    });
  }
  function loadCommands() {
    return once('commands', async () => { const data = await api('commands'); commands = data.commands || []; renderCommands(); });
  }
  $('command-search').addEventListener('input', renderCommands);
  $('command-platform').addEventListener('change', renderCommands);
  for (const [id, name] of [['reload-files', 'reload_files'], ['clean-memory', 'clean_ram']]) {
    $(id).addEventListener('click', event => busy(event.currentTarget, async () => {
      const data = await post('quick_action', { action: name });
      toast(data.message || 'Đã hoàn tất');
      if (name === 'reload_files') await loadFiles(true);
    }));
  }

  // One bounded decorative effect per click; no animation workers or timers per frame.
  document.addEventListener('click', event => {
    const button = event.target.closest('.button, .nav button');
    if (!button || button.disabled || reducedMotion.matches) return;
    const bounds = button.getBoundingClientRect();
    const effect = node('span', undefined, 'ripple');
    effect.setAttribute('aria-hidden', 'true');
    effect.style.left = ((event.detail ? event.clientX - bounds.left : bounds.width / 2)) + 'px';
    effect.style.top = ((event.detail ? event.clientY - bounds.top : bounds.height / 2)) + 'px';
    button.append(effect);
    setTimeout(() => effect.remove(), 650);
  }, { capture: true });
  if (matchMedia('(hover: hover) and (pointer: fine)').matches && !reducedMotion.matches) {
    let pointerFrame;
    document.addEventListener('pointermove', event => {
      if (pointerFrame) return;
      const button = event.target.closest('.button');
      if (!button) return;
      pointerFrame = requestAnimationFrame(() => {
        const bounds = button.getBoundingClientRect();
        button.style.setProperty('--px', event.clientX - bounds.left + 'px');
        button.style.setProperty('--py', event.clientY - bounds.top + 'px');
        pointerFrame = null;
      });
    }, { passive: true });
  }

  fire(refresh());
  let lastPoll = Date.now();
  const refreshTimer = setInterval(() => {
    if (document.hidden) return;
    const stopping = telemetryCache?.tasks?.some(task => task.status === 'stopping');
    if (Date.now() - lastPoll >= (stopping ? 2000 : 10000)) {
      lastPoll = Date.now();
      fire(loadCurrent());
    }
  }, 2000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) fire(loadCurrent()); });
  window.addEventListener('pagehide', () => { clearInterval(refreshTimer); clearTimeout(qrTimer); qrGeneration++; });
})();
