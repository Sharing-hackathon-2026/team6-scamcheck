// Logic giao diện structured cho L1. Không giữ hay hiển thị toàn văn nhật ký AI.
import { check, ApiError } from './api.js';

const textInput = document.getElementById('textInput');
const checkBtn = document.getElementById('checkBtn');
const clearBtn = document.getElementById('clearBtn');
const statusEl = document.getElementById('status');
const resultEl = document.getElementById('result');
const errorEl = document.getElementById('error');
const usageEl = document.getElementById('usage');

const riskLabels = {
  an_toan: 'An toàn',
  nghi_ngo: 'Nghi ngờ',
  nguy_hiem: 'Nguy hiểm',
  khong_lien_quan: 'Không liên quan',
};

function setLoading(on, message = '') {
  checkBtn.disabled = on;
  statusEl.className = `status${on ? ' loading' : ''}`;
  statusEl.textContent = message;
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
  resultEl.hidden = true;
}

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function showResult(detective) {
  resultEl.replaceChildren();
  resultEl.dataset.risk = detective.risk_level;
  const risk = makeElement('p', 'risk-label', `Mức rủi ro: ${riskLabels[detective.risk_level] || 'Nghi ngờ'}`);
  const reason = makeElement('p', 'reason', detective.reason);
  resultEl.append(risk, reason);

  if (detective.red_flags?.length) {
    const flagsHeading = makeElement('h2', '', 'Dấu hiệu cần chú ý');
    const flags = makeElement('ul', 'signal-list');
    detective.red_flags.forEach((flag) => {
      const item = document.createElement('li');
      const title = makeElement('strong', '', flag.label);
      item.append(title, document.createTextNode(` — ${flag.explanation}`));
      if (flag.excerpt) item.append(makeElement('blockquote', '', `“${flag.excerpt}”`));
      flags.append(item);
    });
    resultEl.append(flagsHeading, flags);
  }

  if (detective.actions?.length) {
    const actionsHeading = makeElement('h2', '', 'Việc bác nên làm ngay');
    const actions = makeElement('ol', 'action-list');
    detective.actions.forEach((action) => actions.append(makeElement('li', '', action)));
    resultEl.append(actionsHeading, actions);
  }
  resultEl.hidden = false;
  errorEl.hidden = true;
}

function showUsage(usage) {
  if (!usage) return;
  usageEl.textContent = `Đã dùng ${usage.calls_used}/${usage.call_limit} lượt kiểm tra trong phiên này.`;
}

async function onCheck() {
  const text = textInput.value.trim();
  resultEl.hidden = true;
  errorEl.hidden = true;
  if (!text) return showError('Vui lòng dán nội dung tin nhắn cần kiểm tra.');

  setLoading(true, 'Đang kiểm tra, vui lòng chờ trong giây lát...');
  try {
    const data = await check(text);
    showResult(data.detective);
    showUsage(data.usage);
  } catch (error) {
    showError(error instanceof ApiError ? error.message : 'Có lỗi không xác định. Vui lòng thử lại.');
  } finally {
    setLoading(false);
  }
}

checkBtn.addEventListener('click', onCheck);
clearBtn.addEventListener('click', () => {
  textInput.value = '';
  textInput.focus();
  resultEl.hidden = true;
  errorEl.hidden = true;
  statusEl.textContent = '';
});
textInput.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') onCheck();
});
