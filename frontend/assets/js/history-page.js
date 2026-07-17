import { wirePreferences } from './preferences.js';
import { materialIcon } from './icons.js';
import { API_BASE } from './config.js';

const RISK_SERIES = Object.freeze([
  { key: 'an_toan', label: 'An toàn', className: 'pie-safe' },
  { key: 'nghi_ngo', label: 'Nghi ngờ', className: 'pie-warning' },
  { key: 'nguy_hiem', label: 'Nguy hiểm', className: 'pie-danger' },
  { key: 'khong_lien_quan', label: 'Không liên quan', className: 'pie-neutral' },
]);
const ACTOR_LABELS = Object.freeze({
  detective: 'Thám tử',
  psychologist: 'Cô tâm lý',
  rescuer: 'Người ứng cứu',
  unknown: 'Không xác định',
});
const STATUS_LABELS = Object.freeze({
  complete: 'Hoàn tất',
  error: 'Lỗi gọi AI',
  invalid_response: 'Phản hồi không hợp lệ',
  guarded_fallback: 'Dùng quy trình dự phòng',
});
const RISK_LABELS = Object.freeze(Object.fromEntries(RISK_SERIES.map((item) => [item.key, item.label])));

const elements = {
  dashboard: document.querySelector('.history-dashboard'),
  scope: document.getElementById('historyScope'),
  notice: document.getElementById('historyNotice'),
  error: document.getElementById('historyError'),
  content: document.getElementById('historyContent'),
  checkCount: document.getElementById('checkCount'),
  callCount: document.getElementById('callCount'),
  retentionDays: document.getElementById('retentionDays'),
  pieSegments: document.getElementById('pieSegments'),
  pieLegend: document.getElementById('pieLegend'),
  pieTotal: document.getElementById('pieTotal'),
  actorCounts: document.getElementById('actorCounts'),
  rows: document.getElementById('historyRows'),
  rowCount: document.getElementById('rowCount'),
  empty: document.getElementById('historyEmpty'),
  tableWrap: document.getElementById('historyTableWrap'),
  adminLogin: document.getElementById('adminLogin'),
  adminExports: document.getElementById('adminExports'),
};

function adminLoginUrl() {
  const protocol = location.hostname === 'localhost' || location.hostname === '127.0.0.1'
    ? 'http:' : 'https:';
  const origin = `${protocol}//${location.hostname}:8001`;
  return `${origin}/__exe.dev/login?redirect=${encodeURIComponent('/history.html?scope=all')}`;
}

function requestedScope() {
  const query = new URLSearchParams(location.search);
  return query.get('scope') === 'all' ? 'all' : 'self';
}

function formatDate(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Không rõ';
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'short',
    timeStyle: 'medium',
  }).format(parsed);
}

function createElement(tag, text = '', className = '') {
  const element = document.createElement(tag);
  if (text) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function renderPie(riskCounts = {}) {
  elements.pieSegments.replaceChildren();
  elements.pieLegend.replaceChildren();
  const total = RISK_SERIES.reduce((sum, item) => sum + Number(riskCounts[item.key] || 0), 0);
  elements.pieTotal.textContent = String(total);
  let offset = 0;
  RISK_SERIES.forEach((series) => {
    const amount = Number(riskCounts[series.key] || 0);
    const percent = total ? (amount / total) * 100 : 0;
    if (percent > 0) {
      const segment = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      segment.setAttribute('class', `risk-pie-segment ${series.className}`);
      segment.setAttribute('cx', '60');
      segment.setAttribute('cy', '60');
      segment.setAttribute('r', '44');
      segment.setAttribute('pathLength', '100');
      segment.setAttribute('stroke-dasharray', `${percent} ${100 - percent}`);
      segment.setAttribute('stroke-dashoffset', String(-offset));
      segment.setAttribute('transform', 'rotate(-90 60 60)');
      elements.pieSegments.append(segment);
      offset += percent;
    }
    const legend = createElement('li');
    legend.append(
      createElement('span', '', `risk-legend-swatch ${series.className}`),
      createElement('span', series.label),
      createElement('strong', `${amount} (${total ? Math.round(percent) : 0}%)`),
    );
    elements.pieLegend.append(legend);
  });
}

function renderActors(actorCounts = {}) {
  elements.actorCounts.replaceChildren();
  Object.entries(ACTOR_LABELS).forEach(([key, label]) => {
    if (key === 'unknown' && !actorCounts[key]) return;
    const row = createElement('div');
    row.append(createElement('dt', label), createElement('dd', String(actorCounts[key] || 0)));
    elements.actorCounts.append(row);
  });
}

function renderLogs(logs, isAdmin) {
  elements.rows.replaceChildren();
  const ordered = [...logs].reverse();
  ordered.forEach((log) => {
    const row = document.createElement('tr');
    row.append(
      createElement('td', formatDate(log.at)),
      createElement('td', ACTOR_LABELS[log.actor] || 'Không xác định'),
      createElement('td', STATUS_LABELS[log.status] || log.status || 'Không rõ'),
      createElement('td', RISK_LABELS[log.risk_level] || '—'),
      createElement('td', `${Number(log.input_length || 0)} ký tự`),
      createElement('td', log.summary || '—'),
    );
    if (isAdmin && log.session_id) {
      row.firstElementChild.title = `Phiên: ${log.session_id}`;
    }
    elements.rows.append(row);
  });
  elements.rowCount.textContent = `${logs.length} dòng gần nhất`;
  elements.empty.hidden = logs.length !== 0;
  elements.tableWrap.hidden = logs.length === 0;
}

function render(data) {
  const stats = data.stats || {};
  const isAdmin = data.scope === 'all';
  elements.scope.textContent = isAdmin ? 'Toàn hệ thống · quản trị' : 'Lịch sử của phiên này';
  elements.notice.textContent = isAdmin
    ? `Đã xác thực ${data.admin_email}. Bảng hiển thị tối đa 500 dòng mới nhất.`
    : 'Chỉ trình duyệt đang dùng mới xem được phiên này. Cache hit không tạo lượt gọi AI giả.';
  elements.checkCount.textContent = String(stats.checks || 0);
  elements.callCount.textContent = String(stats.ai_calls || 0);
  elements.retentionDays.textContent = `${stats.retention_days || 30} ngày`;
  renderPie(stats.risk_counts || {});
  renderActors(stats.actor_counts || {});
  renderLogs(Array.isArray(data.logs) ? data.logs : [], isAdmin);
  elements.adminExports.hidden = !isAdmin;
  elements.adminLogin.classList.toggle('is-authorized', isAdmin);
  elements.adminLogin.setAttribute(
    'aria-label',
    isAdmin ? `Đã đăng nhập quản trị: ${data.admin_email}` : 'Đăng nhập quản trị bằng exe.dev',
  );
  elements.content.hidden = false;
  elements.error.hidden = true;
}

function renderError(message, loginUrl = '') {
  elements.content.hidden = true;
  elements.error.replaceChildren(createElement('p', message || 'Chưa tải được lịch sử AI.'));
  if (loginUrl) {
    const login = createElement('a', 'Đăng nhập quản trị bằng exe.dev', 'button-secondary');
    login.href = loginUrl;
    login.prepend(materialIcon('shield', { className: 'icon-glyph' }));
    elements.error.append(login);
  } else {
    const retry = createElement('button', 'Thử tải lại', 'button-secondary');
    retry.type = 'button';
    retry.prepend(materialIcon('refresh', { className: 'icon-glyph' }));
    retry.addEventListener('click', loadHistory);
    elements.error.append(retry);
  }
  elements.error.hidden = false;
}

async function loadHistory() {
  const scope = requestedScope();
  elements.dashboard.setAttribute('aria-busy', 'true');
  elements.error.hidden = true;
  try {
    const response = await fetch(`${API_BASE}/api/ai-logs?scope=${scope}`, {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      renderError(data.error || 'Chưa tải được lịch sử AI.', data.login_url || '');
      return;
    }
    render(data);
  } catch {
    renderError('Không kết nối được tới máy chủ. Bác vui lòng kiểm tra mạng rồi thử lại.');
  } finally {
    elements.dashboard.setAttribute('aria-busy', 'false');
  }
}

elements.adminLogin.href = adminLoginUrl();
const displayPrefs = document.getElementById('displayPrefs');
if (displayPrefs) wirePreferences({ root: displayPrefs });
loadHistory();
