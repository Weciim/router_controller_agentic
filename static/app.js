const state = {
  bootstrap: null,
  plan: null,
  applied: null,
};

const els = {
  promptInput: document.getElementById('promptInput'),
  previewBtn: document.getElementById('previewBtn'),
  applyBtn: document.getElementById('applyBtn'),
  applyLiveToggle: document.getElementById('applyLiveToggle'),
  bootstrapSummary: document.getElementById('bootstrapSummary'),
  previewSummary: document.getElementById('previewSummary'),
  applySummary: document.getElementById('applySummary'),
  previewJson: document.getElementById('previewJson'),
  applyJson: document.getElementById('applyJson'),
  supportedAppsCount: document.getElementById('supportedAppsCount'),
  deviceCount: document.getElementById('deviceCount'),
  qosReady: document.getElementById('qosReady'),
  routerPill: document.getElementById('routerPill'),
};

async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

function badge(text, tone = 'muted') {
  return `<span class="pill ${tone}">${escapeHtml(text)}</span>`;
}

function escapeHtml(str) {
  return String(str ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderBootstrap(data) {
  state.bootstrap = data;
  els.supportedAppsCount.textContent = data.supported_apps?.length ?? 0;
  els.deviceCount.textContent = data.available_devices?.length ?? 0;
  els.qosReady.textContent = data.qos_probe?.ok ? 'Yes' : 'Needs setup';
  els.routerPill.className = `pill ${data.backend_summary?.ready ? 'success' : 'warning'}`;
  els.routerPill.textContent = data.backend_summary?.ready ? 'Router ready' : 'Partial readiness';

  const blocks = [
    ['Router host', data.router?.host],
    ['Router user', data.router?.user],
    ['Password set', data.router?.password_set ? 'Yes' : 'No'],
    ['QoS backend', data.qos_probe?.ok ? 'Detected' : 'Not fully ready'],
    ['Real apply', data.real_apply_probe?.ok ? 'Ready' : 'Limited'],
    ['Supported apps', (data.supported_apps || []).slice(0, 8).join(', ') || 'None'],
  ];

  els.bootstrapSummary.innerHTML = blocks.map(([label, value]) => `
    <div class="metric">
      <span class="metric-label">${escapeHtml(label)}</span>
      <strong>${escapeHtml(value ?? '—')}</strong>
    </div>
  `).join('');
}

function renderPreview(data) {
  state.plan = data;
  els.previewJson.textContent = prettyJson(data);
  els.applyBtn.disabled = !!data.unsupported_application;

  if (data.mode === 'clarification') {
    els.previewSummary.innerHTML = `
      <div class="info-banner">Clarification needed before execution.</div>
      <div class="empty-state">${escapeHtml(data.clarification_question || data.clarification?.message || 'The backend needs more detail.')}</div>
    `;
    return;
  }

  const validated = data.validated || {};
  const match = data.resolution?.device || {};
  const gate = data.gated_exec_spec?.backend_gate || {};
  const appRes = data.app_resolution || {};
  const unsupported = !!data.unsupported_application;

  els.previewSummary.innerHTML = `
    ${unsupported ? `<div class="info-banner">This app is not supported yet for QoS. Available apps: ${(data.supported_apps || []).join(', ')}</div>` : ''}
    <div class="kv-grid">
      <div class="kv"><span>Intent</span><strong>${escapeHtml(validated.intent || '—')}</strong></div>
      <div class="kv"><span>Target device</span><strong>${escapeHtml(match.hostname || match.name || validated.target_device || '—')}</strong></div>
      <div class="kv"><span>App / service</span><strong>${escapeHtml(appRes.canonical_name || validated.application || validated.service || '—')}</strong></div>
      <div class="kv"><span>Live apply ready</span><strong>${escapeHtml(String(!!gate.real_apply_ready))}</strong></div>
      <div class="kv"><span>Schedule</span><strong>${escapeHtml(formatSchedule(validated.schedule || data.exec_spec?.schedule || data.gated_exec_spec?.schedule))}</strong></div>
      <div class="kv"><span>Action</span><strong>${escapeHtml(validated.policy?.action || data.exec_spec?.policy?.action || '—')}</strong></div>
    </div>
    <div class="list-inline" style="margin-top:16px;">
      ${badge(gate.real_apply_ready ? 'Live apply available' : 'Dry-run only', gate.real_apply_ready ? 'success' : 'warning')}
      ${appRes.known ? badge(`Resolved app: ${appRes.canonical_name}`, 'success') : ''}
      ${data.resolution?.warning ? badge(data.resolution.warning, 'warning') : ''}
    </div>
  `;
}

function renderApply(data) {
  state.applied = data;
  els.applyJson.textContent = prettyJson(data);

  const result = data.result || {};
  const apply = result.apply_result || {};
  const verify = result.verify_result || {};
  const device = result.device || {};
  const app = result.application_resolution || {};

  els.applySummary.innerHTML = `
    <div class="info-banner">${escapeHtml(result.user_message || 'Execution complete.')}</div>
    <div class="kv-grid">
      <div class="kv"><span>Applied</span><strong>${escapeHtml(String(!!apply.applied))}</strong></div>
      <div class="kv"><span>Verified</span><strong>${escapeHtml(String(!!verify.verified))}</strong></div>
      <div class="kv"><span>Schedule verified</span><strong>${escapeHtml(String(verify.schedule_verified))}</strong></div>
      <div class="kv"><span>Device</span><strong>${escapeHtml(device.hostname || device.name || '—')}</strong></div>
      <div class="kv"><span>Application</span><strong>${escapeHtml(app.canonical_name || apply.writer_plan?.application || '—')}</strong></div>
      <div class="kv"><span>Rule path</span><strong class="code-inline">${escapeHtml(apply.writer_plan?.remote_path || '—')}</strong></div>
      <div class="kv"><span>Pre snapshot</span><strong>${escapeHtml(result.pre_snapshot?.snapshot_id || '—')}</strong></div>
      <div class="kv"><span>Post snapshot</span><strong>${escapeHtml(result.post_snapshot?.snapshot_id || '—')}</strong></div>
    </div>
  `;
}

function formatSchedule(schedule) {
  if (!schedule) return '—';
  const days = Array.isArray(schedule.days) ? schedule.days.join(', ') : '—';
  const start = schedule.start_time || '—';
  const end = schedule.end_time || '—';
  return `${days} · ${start}–${end}`;
}

async function loadBootstrap() {
  try {
    const res = await api('/api/bootstrap');
    renderBootstrap(res.data);
  } catch (err) {
    els.routerPill.className = 'pill error';
    els.routerPill.textContent = 'Bootstrap failed';
    els.bootstrapSummary.innerHTML = `<div class="empty-state">${escapeHtml(err.error || 'Failed to load backend status.')}</div>`;
  }
}

async function previewPlan() {
  const prompt = els.promptInput.value.trim();
  if (!prompt) return;
  els.previewBtn.disabled = true;
  els.previewBtn.textContent = 'Generating...';
  try {
    const data = await api('/api/plan', {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    });
    renderPreview(data);
  } catch (err) {
    els.previewSummary.innerHTML = `<div class="empty-state">${escapeHtml(err.error || 'Preview failed.')}</div>`;
    els.previewJson.textContent = prettyJson(err);
  } finally {
    els.previewBtn.disabled = false;
    els.previewBtn.textContent = 'Preview plan';
  }
}

async function applyPlan() {
  const prompt = els.promptInput.value.trim();
  if (!prompt) return;
  els.applyBtn.disabled = true;
  els.applyBtn.textContent = 'Applying...';
  try {
    const data = await api('/api/apply', {
      method: 'POST',
      body: JSON.stringify({
        prompt,
        approve: true,
        apply_live: els.applyLiveToggle.checked,
      }),
    });
    renderApply(data);
  } catch (err) {
    els.applySummary.innerHTML = `<div class="empty-state">${escapeHtml(err.error || 'Apply failed.')}</div>`;
    els.applyJson.textContent = prettyJson(err);
  } finally {
    els.applyBtn.disabled = false;
    els.applyBtn.textContent = 'Apply from browser';
  }
}

function setQuickPrompts() {
  document.querySelectorAll('[data-prompt]').forEach((btn) => {
    btn.addEventListener('click', () => {
      els.promptInput.value = btn.dataset.prompt || '';
    });
  });
}

function setTabs() {
  document.querySelectorAll('.tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach((el) => el.classList.remove('active'));
      document.querySelectorAll('.json-view').forEach((el) => el.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.tab).classList.add('active');
    });
  });
}

function setTheme() {
  const btn = document.querySelector('[data-theme-toggle]');
  let theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', theme);
  btn.addEventListener('click', () => {
    theme = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme);
  });
}

els.previewBtn.addEventListener('click', previewPlan);
els.applyBtn.addEventListener('click', applyPlan);
setQuickPrompts();
setTabs();
setTheme();
loadBootstrap();