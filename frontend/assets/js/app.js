import { check, ApiError } from './api.js';
import { renderHighlightedText } from './highlight-excerpts.js';
import {
  addHistoryEntry,
  clearHistory,
  deleteHistoryEntry,
  loadHistory,
  saveHistory,
} from './history.js';
import { normalizeDetective, RISK_META } from './result-model.js';
import {
  appendTranscript,
  getSpeechRecognitionConstructor,
  SPEECH_MESSAGES,
  speechErrorMessage,
  transcriptFromEvent,
} from './speech.js';

const samples = Object.freeze({
  danger: 'THÔNG BÁO KHẨN: Tài khoản ngân hàng của quý khách sẽ bị khoá sau 30 phút. Bấm https://xac-minh-ngay.example và cung cấp mã OTP để duy trì dịch vụ.',
  suspicious: 'Chúc mừng số điện thoại của bạn trúng xe máy trị giá 60 triệu đồng. Vui lòng chuyển trước 500.000 đồng phí nhận thưởng trong hôm nay.',
  safe: 'Đơn hàng 12345 dự kiến giao từ 14:00 đến 16:00 hôm nay. Nhân viên giao hàng sẽ gọi khi đến. Quý khách không cần chuyển khoản trước.',
});

const elements = {
  textInput: document.getElementById('textInput'),
  checkBtn: document.getElementById('checkBtn'),
  clearBtn: document.getElementById('clearBtn'),
  speechBtn: document.getElementById('speechBtn'),
  speechBtnLabel: document.getElementById('speechBtnLabel'),
  speechStatus: document.getElementById('speechStatus'),
  status: document.getElementById('status'),
  usage: document.getElementById('usage'),
  error: document.getElementById('error'),
  loadingPanel: document.getElementById('loadingPanel'),
  result: document.getElementById('result'),
  historyList: document.getElementById('historyList'),
  historyEmpty: document.getElementById('historyEmpty'),
  clearHistoryBtn: document.getElementById('clearHistoryBtn'),
};

let historyEntries = loadHistory(window.localStorage);
let recognition = null;
let isListening = false;

function createElement(tag, { className = '', text = '', attributes = {} } = {}) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
  return element;
}

function riskIcon() {
  const svgNamespace = 'http://www.w3.org/2000/svg';
  const wrapper = createElement('span', { className: 'risk-icon', attributes: { 'aria-hidden': 'true' } });
  const svg = document.createElementNS(svgNamespace, 'svg');
  svg.setAttribute('width', '24');
  svg.setAttribute('height', '24');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  const paths = ['M12 3 20 6v5c0 5-3.4 8.3-8 10-4.6-1.7-8-5-8-10V6l8-3Z', 'M12 8v5M12 17h.01'];
  paths.forEach((data) => {
    const path = document.createElementNS(svgNamespace, 'path');
    path.setAttribute('d', data);
    svg.append(path);
  });
  wrapper.append(svg);
  return wrapper;
}

function deleteIcon() {
  const svgNamespace = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNamespace, 'svg');
  svg.setAttribute('width', '24');
  svg.setAttribute('height', '24');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  const paths = ['M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6', 'M10 11v5M14 11v5'];
  paths.forEach((data) => {
    const path = document.createElementNS(svgNamespace, 'path');
    path.setAttribute('d', data);
    svg.append(path);
  });
  return svg;
}

function setLoading(on) {
  elements.checkBtn.disabled = on;
  elements.textInput.setAttribute('aria-busy', String(on));
  elements.loadingPanel.hidden = !on;
  elements.status.textContent = on ? 'Đang kiểm tra, thường mất vài giây.' : '';
  if (on) {
    elements.result.hidden = true;
    elements.error.hidden = true;
  }
}

function showError(message) {
  elements.error.textContent = message;
  elements.error.hidden = false;
  elements.result.hidden = true;
  elements.error.focus({ preventScroll: true });
}

function showUsage(usage) {
  if (!usage || !Number.isFinite(usage.calls_used) || !Number.isFinite(usage.call_limit)) {
    elements.usage.textContent = '';
    return;
  }
  elements.usage.textContent = `Đã dùng ${usage.calls_used}/${usage.call_limit} lượt kiểm tra trong phiên này.`;
}

function appendRiskCard(container, detective) {
  const meta = RISK_META[detective.risk_level];
  const card = createElement('div', {
    className: 'risk-card',
    attributes: { 'data-risk': detective.risk_level, role: 'group', 'aria-label': meta.announcement },
  });
  const copy = createElement('div');
  copy.append(
    createElement('p', { className: 'risk-eyebrow', text: 'Mức rủi ro' }),
    createElement('h2', { className: 'risk-label', text: meta.label }),
    createElement('p', { className: 'reason', text: detective.reason }),
  );
  card.append(riskIcon(), copy);
  container.append(card);
}

function appendSourceMessage(container, text, detective) {
  const section = createElement('section', { className: 'result-section' });
  section.append(createElement('h3', { text: 'Đoạn đáng chú ý trong tin gốc' }));
  const source = createElement('p', { className: 'source-message' });
  const excerpts = detective.red_flags.map((flag) => flag.excerpt).filter(Boolean);
  renderHighlightedText(source, text, excerpts);
  section.append(source);
  container.append(section);
}

function appendSignals(container, detective) {
  const section = createElement('section', { className: 'result-section' });
  section.append(createElement('h3', { text: 'Dấu hiệu cần chú ý' }));
  if (!detective.red_flags.length) {
    section.append(createElement('p', {
      className: 'no-signals',
      text: detective.risk_level === 'khong_lien_quan'
        ? 'Nội dung này không thuộc nhóm tin cần kiểm tra lừa đảo.'
        : 'Không có dấu hiệu cụ thể nào được trích ra từ tin nhắn.',
    }));
  } else {
    const list = createElement('ul', { className: 'signal-list' });
    detective.red_flags.forEach((flag) => {
      const item = createElement('li');
      item.append(createElement('span', { className: 'signal-label', text: flag.label }));
      if (flag.explanation) item.append(document.createTextNode(` — ${flag.explanation}`));
      list.append(item);
    });
    section.append(list);
  }
  container.append(section);
}

function appendActions(container, detective) {
  if (!detective.actions.length) return;
  const section = createElement('section', { className: 'result-section' });
  section.append(createElement('h3', { text: 'Ba việc bác nên làm ngay' }));
  const list = createElement('ol', { className: 'action-list' });
  detective.actions.forEach((action) => list.append(createElement('li', { text: action })));
  section.append(list);
  container.append(section);
}

function showResult(text, rawDetective, { focus = true } = {}) {
  const detective = normalizeDetective(rawDetective);
  elements.result.replaceChildren();
  elements.result.dataset.risk = detective.risk_level;
  appendRiskCard(elements.result, detective);
  appendSourceMessage(elements.result, text, detective);
  appendSignals(elements.result, detective);
  appendActions(elements.result, detective);
  elements.result.hidden = false;
  elements.error.hidden = true;
  if (focus) elements.result.focus({ preventScroll: true });
  return detective;
}

function previewText(text) {
  const collapsed = text.replace(/\s+/g, ' ').trim();
  return collapsed.length > 92 ? `${collapsed.slice(0, 89)}…` : collapsed;
}

function renderHistory() {
  elements.historyList.replaceChildren();
  const isEmpty = historyEntries.length === 0;
  elements.historyEmpty.hidden = !isEmpty;
  elements.clearHistoryBtn.hidden = isEmpty;

  historyEntries.forEach((entry) => {
    const detective = normalizeDetective(entry.detective);
    const item = createElement('li', { className: 'history-item' });
    const openButton = createElement('button', {
      className: 'history-open',
      attributes: { type: 'button', 'data-history-open': entry.id },
    });
    openButton.append(
      createElement('span', { className: 'history-risk', text: RISK_META[detective.risk_level].label }),
      createElement('span', { className: 'history-preview', text: previewText(entry.text) }),
    );
    const removeButton = createElement('button', {
      className: 'icon-button danger',
      attributes: {
        type: 'button',
        'data-history-delete': entry.id,
        'aria-label': `Xoá mục lịch sử: ${previewText(entry.text)}`,
        title: 'Xoá mục này',
      },
    });
    removeButton.append(deleteIcon());
    item.append(openButton, removeButton);
    elements.historyList.append(item);
  });
}

function persistHistory() {
  saveHistory(window.localStorage, historyEntries);
  renderHistory();
}

function stopSpeech() {
  if (recognition && isListening) recognition.stop();
}

function clearCurrent() {
  stopSpeech();
  elements.textInput.value = '';
  elements.result.hidden = true;
  elements.error.hidden = true;
  elements.loadingPanel.hidden = true;
  elements.status.textContent = '';
  elements.usage.textContent = '';
  elements.textInput.focus();
}

async function onCheck() {
  const text = elements.textInput.value.trim();
  if (!text) {
    showError('Vui lòng dán, gõ hoặc đọc nội dung tin nhắn cần kiểm tra.');
    return;
  }

  stopSpeech();
  setLoading(true);
  try {
    const data = await check(text);
    const detective = showResult(text, data.detective);
    historyEntries = addHistoryEntry(historyEntries, { text, detective });
    persistHistory();
    showUsage(data.usage);
  } catch (error) {
    showError(error instanceof ApiError ? error.message : 'Có lỗi không xác định. Vui lòng thử lại.');
  } finally {
    setLoading(false);
  }
}

function openHistoryEntry(id) {
  const entry = historyEntries.find((item) => item.id === id);
  if (!entry) return;
  stopSpeech();
  elements.textInput.value = entry.text;
  showResult(entry.text, entry.detective);
  elements.status.textContent = 'Đang xem lại kết quả đã lưu trên thiết bị. Không gọi AI.';
  elements.usage.textContent = '';
}

function setupSpeech() {
  const SpeechRecognition = getSpeechRecognitionConstructor(window);
  if (!SpeechRecognition) {
    elements.speechBtn.disabled = true;
    elements.speechBtn.hidden = true;
    elements.speechStatus.textContent = SPEECH_MESSAGES.unsupported;
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = 'vi-VN';
  recognition.continuous = true;
  recognition.interimResults = false;

  recognition.addEventListener('start', () => {
    isListening = true;
    elements.speechBtn.setAttribute('aria-pressed', 'true');
    elements.speechBtnLabel.textContent = 'Dừng nghe';
    elements.speechStatus.dataset.state = 'listening';
    elements.speechStatus.textContent = SPEECH_MESSAGES.listening;
  });

  recognition.addEventListener('result', (event) => {
    const transcript = transcriptFromEvent(event);
    if (transcript) elements.textInput.value = appendTranscript(elements.textInput.value, transcript);
  });

  recognition.addEventListener('error', (event) => {
    elements.speechStatus.dataset.state = 'error';
    elements.speechStatus.textContent = speechErrorMessage(event.error);
  });

  recognition.addEventListener('end', () => {
    isListening = false;
    elements.speechBtn.setAttribute('aria-pressed', 'false');
    elements.speechBtnLabel.textContent = 'Nhập bằng giọng nói';
    if (elements.speechStatus.dataset.state === 'listening') {
      elements.speechStatus.dataset.state = 'idle';
      elements.speechStatus.textContent = SPEECH_MESSAGES.stopped;
    }
  });

  elements.speechBtn.addEventListener('click', () => {
    if (isListening) {
      recognition.stop();
      return;
    }
    elements.speechStatus.dataset.state = 'idle';
    elements.speechStatus.textContent = '';
    try {
      recognition.start();
    } catch {
      elements.speechStatus.textContent = SPEECH_MESSAGES.generic;
    }
  });
}

elements.checkBtn.addEventListener('click', onCheck);
elements.clearBtn.addEventListener('click', clearCurrent);
elements.textInput.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') onCheck();
});

document.querySelectorAll('[data-sample]').forEach((button) => {
  button.addEventListener('click', () => {
    elements.textInput.value = samples[button.dataset.sample] || '';
    elements.textInput.focus();
    elements.status.textContent = 'Đã điền tin mẫu. Bấm “Kiểm tra tin nhắn” để phân tích.';
  });
});

elements.historyList.addEventListener('click', (event) => {
  const openButton = event.target.closest('[data-history-open]');
  if (openButton) {
    openHistoryEntry(openButton.dataset.historyOpen);
    return;
  }
  const deleteButton = event.target.closest('[data-history-delete]');
  if (!deleteButton) return;
  const entry = historyEntries.find((item) => item.id === deleteButton.dataset.historyDelete);
  if (!entry || !window.confirm('Xoá kết quả này khỏi lịch sử trên thiết bị?')) return;
  historyEntries = deleteHistoryEntry(historyEntries, entry.id);
  persistHistory();
  elements.status.textContent = 'Đã xoá một mục lịch sử.';
});

elements.clearHistoryBtn.addEventListener('click', () => {
  if (!historyEntries.length || !window.confirm('Xoá toàn bộ lịch sử đã kiểm tra trên thiết bị này?')) return;
  historyEntries = clearHistory();
  persistHistory();
  elements.status.textContent = 'Đã xoá toàn bộ lịch sử.';
});

renderHistory();
setupSpeech();
