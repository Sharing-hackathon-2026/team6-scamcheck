function renderLibrary(group = 'all') {
  const groups = libraryData.groups.map((item) => item.key);
  const activeGroup = groups.includes(group) ? group : 'all';
  elements.libraryFilters.replaceChildren();
  [{ key: 'all', label: 'Tất cả' }, ...libraryData.groups].forEach((filter) => {
    const button = createElement('button', {
      className: 'library-filter',
      text: filter.label,
      attributes: {
        type: 'button',
        'data-library-group': filter.key,
        'aria-pressed': String(filter.key === activeGroup),
      },
    });
    elements.libraryFilters.append(button);
  });

  const items = filterLibraryItems(libraryData.items, activeGroup);
  elements.libraryList.replaceChildren();
  items.forEach((item) => {
    const article = createElement('details', {
      className: 'library-item',
      attributes: { id: item.slug, 'data-library-item': item.id },
    });
    const summary = createElement('summary', { className: 'library-item-summary' });
    const summaryCopy = createElement('span');
    summaryCopy.append(
      createElement('span', {
        className: 'library-group-label',
        text: libraryData.groups.find((groupItem) => groupItem.key === item.group)?.label || '',
      }),
      createElement('span', { className: 'library-item-title', text: item.title }),
    );
    summary.append(summaryCopy, createElement('span', {
      className: 'library-toggle-label', text: 'Xem dấu hiệu', attributes: { 'aria-hidden': 'true' },
    }));
    const content = createElement('div', { className: 'library-item-content' });
    content.append(createElement('p', { text: item.summary }));
    const signs = createElement('ul', { className: 'library-signs' });
    item.warning_signs.forEach((sign) => signs.append(createElement('li', { text: sign })));
    content.append(
      signs,
      createElement('p', { className: 'library-safe-action', text: `Nên làm: ${item.safe_action}` }),
    );
    article.append(summary, content);
    elements.libraryList.append(article);
  });
  elements.libraryStatus.textContent = `Đang hiển thị ${items.length} kiểu lừa đảo.`;
}

async function setupLibrary() {
  try {
    libraryData = await getScamLibrary();
    const groups = libraryData.groups.map((item) => item.key);
    renderLibrary(libraryGroupFromHash(window.location.hash, groups));
  } catch (error) {
    elements.libraryStatus.textContent = '';
    elements.libraryError.textContent = error instanceof ApiError
      ? error.message
      : 'Chưa tải được thư viện. Bác vui lòng thử lại sau.';
    elements.libraryError.hidden = false;
  }
}

// Logic giao diện Stage 2. Chuẩn hoá NFC ở mọi boundary để tránh browser render Unicode tổ hợp sai.
import { check, ApiError, getScamLibrary } from './api.js';
import { renderHighlightedText } from './highlight-excerpts.js';
import {
  addHistoryEntry,
  clearHistory,
  deleteHistoryEntry,
  loadHistory,
  saveHistory,
} from './history.js';
import { normalizeDetective, RISK_META } from './result-model.js';
import { normalizePsychologist, filterLibraryItems, libraryGroupFromHash } from './stage3-model.js';
import { normalizeTechnicalAnalysis } from './stage4-model.js';
import { normalizeNfc } from './unicode.js';
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
  error: document.getElementById('error'),
  loadingPanel: document.getElementById('loadingPanel'),
  cancelCheckBtn: document.getElementById('cancelCheckBtn'),
  result: document.getElementById('result'),
  historyList: document.getElementById('historyList'),
  historyEmpty: document.getElementById('historyEmpty'),
  clearHistoryBtn: document.getElementById('clearHistoryBtn'),
  libraryPanel: document.getElementById('library'),
  libraryContent: document.getElementById('libraryContent'),
  libraryToggleBtn: document.getElementById('libraryToggleBtn'),
  libraryFilters: document.getElementById('libraryFilters'),
  libraryList: document.getElementById('libraryList'),
  libraryStatus: document.getElementById('libraryStatus'),
  libraryError: document.getElementById('libraryError'),
};

let libraryData = { groups: [], items: [] };

let historyEntries = loadHistory(window.localStorage);
let recognition = null;
let isListening = false;
let activeController = null;
let progressTimers = [];

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

function stopProgress() {
  progressTimers.forEach((timer) => window.clearTimeout(timer));
  progressTimers = [];
}

function startProgress() {
  stopProgress();
  const stages = [
    [0, 'Đang chuẩn hoá tin nhắn và kiểm tra dữ liệu…'],
    [700, 'Đang soi đường dẫn và đối chiếu tên miền…'],
    [1800, 'Đang đối chiếu OTP, chuyển tiền và dấu hiệu thúc giục…'],
    [3200, 'Thám tử đang phân tích. Nếu cần, Cô tâm lý sẽ giải thích tiếp…'],
  ];
  stages.forEach(([delay, message]) => {
    progressTimers.push(window.setTimeout(() => {
      elements.status.textContent = message;
    }, delay));
  });
}

function setLoading(on) {
  elements.checkBtn.disabled = on;
  elements.textInput.setAttribute('aria-busy', String(on));
  elements.loadingPanel.hidden = !on;
  if (!on) stopProgress();
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
    createElement('p', {
      className: 'risk-qualifier',
      text: 'Đây là kết quả hỗ trợ, không phải xác nhận chính thức.',
    }),
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

function appendTechnicalAnalysis(container, rawTechnical) {
  const technical = normalizeTechnicalAnalysis(rawTechnical);
  if (!technical.links.length && !technical.ruleSignals.length) return;
  const section = createElement('details', { className: 'result-section technical-analysis' });
  const summary = createElement('summary', {
    className: 'technical-summary',
    text: 'Xem kiểm tra kỹ thuật',
  });
  const content = createElement('div', { className: 'technical-content' });
  content.append(createElement('p', {
    className: 'technical-note',
    text: 'Các tín hiệu dưới đây hỗ trợ Thám tử; một dấu hiệu đơn lẻ không tự khẳng định người gửi là lừa đảo.',
  }));
  if (technical.links.length) {
    content.append(createElement('h4', { text: 'Đường dẫn được tìm thấy' }));
    const links = createElement('ul', { className: 'technical-list' });
    technical.links.forEach((link) => {
      const domainText = link.resolved && link.final_domain !== link.original_domain
        ? `${link.original_domain} → ${link.final_domain}`
        : link.original_domain;
      const item = createElement('li');
      item.append(createElement('strong', { text: domainText || link.source_url }));
      link.warnings.forEach((warning) => item.append(
        createElement('span', { className: 'technical-warning', text: warning.reason }),
      ));
      links.append(item);
    });
    content.append(links);
  }
  if (technical.ruleSignals.length) {
    content.append(createElement('h4', { text: 'Luật an toàn phát hiện' }));
    const signals = createElement('ul', { className: 'technical-list' });
    technical.ruleSignals.forEach((signal) => {
      const item = createElement('li', { attributes: { 'data-severity': signal.severity } });
      item.append(
        createElement('strong', { text: signal.label }),
        createElement('span', { text: signal.explanation }),
      );
      signals.append(item);
    });
    content.append(signals);
  }
  section.append(summary, content);
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
  const section = createElement('section', { className: 'result-section immediate-actions' });
  section.append(createElement('h3', { text: 'Ba việc bác nên làm ngay' }));
  const list = createElement('ol', { className: 'action-list' });
  detective.actions.forEach((action) => list.append(createElement('li', { text: action })));
  section.append(list);
  container.append(section);
}

function appendPsychologist(container, rawPsychologist, status, error) {
  const psychologist = normalizePsychologist(rawPsychologist, status, error);
  if (psychologist.status === 'not_needed') return;
  const section = createElement('section', {
    className: 'psychologist-card',
    attributes: { 'aria-labelledby': 'psychologistTitle' },
  });
  section.append(
    createElement('p', { className: 'section-eyebrow', text: 'Góc nhìn thứ hai' }),
    createElement('h3', { text: 'Cô tâm lý giải thích', attributes: { id: 'psychologistTitle' } }),
  );
  if (psychologist.status === 'complete') {
    section.append(createElement('p', { className: 'psychologist-message', text: psychologist.message }));
  } else {
    section.append(createElement('p', {
      className: 'psychologist-unavailable',
      text: psychologist.error || 'Cô tâm lý chưa thể giải thích thêm; kết quả Thám tử vẫn đầy đủ.',
    }));
  }
  container.append(section);
}

function showResult(text, rawDetective, psychologistOptions = {}, { focus = true } = {}) {
  const detective = normalizeDetective(rawDetective);
  elements.result.replaceChildren();
  elements.result.dataset.risk = detective.risk_level;
  appendRiskCard(elements.result, detective);
  appendActions(elements.result, detective);
  appendSourceMessage(elements.result, text, detective);
  appendSignals(elements.result, detective);
  appendPsychologist(
    elements.result,
    psychologistOptions.psychologist,
    psychologistOptions.status,
    psychologistOptions.error,
  );
  appendTechnicalAnalysis(elements.result, psychologistOptions.technicalAnalysis);
  setLibraryCollapsed(true);
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
    const normalizedText = normalizeNfc(entry.text);
    const item = createElement('li', { className: 'history-item' });
    const openButton = createElement('button', {
      className: 'history-open',
      attributes: { type: 'button', 'data-history-open': entry.id },
    });
    openButton.append(
      createElement('span', { className: 'history-risk', text: RISK_META[detective.risk_level].label }),
      createElement('span', { className: 'history-preview', text: previewText(normalizedText) }),
    );
    const removeButton = createElement('button', {
      className: 'icon-button danger',
      attributes: {
        type: 'button',
        'data-history-delete': entry.id,
        'aria-label': `Xoá mục lịch sử: ${previewText(normalizedText)}`,
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

function setLibraryCollapsed(collapsed) {
  elements.libraryPanel.dataset.collapsed = String(collapsed);
  elements.libraryContent.hidden = collapsed;
  elements.libraryToggleBtn.setAttribute('aria-expanded', String(!collapsed));
  elements.libraryToggleBtn.textContent = collapsed ? 'Mở thư viện' : 'Thu gọn thư viện';
}

function clearCurrent() {
  stopSpeech();
  if (activeController) activeController.abort();
  elements.textInput.value = '';
  elements.result.hidden = true;
  elements.error.hidden = true;
  elements.loadingPanel.hidden = true;
  elements.status.textContent = '';
  setLibraryCollapsed(false);
  elements.textInput.focus();
}

async function onCheck() {
  elements.textInput.value = normalizeNfc(elements.textInput.value);
  const text = elements.textInput.value.trim();
  if (!text) {
    showError('Vui lòng dán, gõ hoặc đọc nội dung tin nhắn cần kiểm tra.');
    return;
  }

  stopSpeech();
  activeController = new AbortController();
  setLoading(true);
  startProgress();
  try {
    const data = await check(text, { signal: activeController.signal });
    const detective = showResult(text, data.detective, {
      psychologist: data.psychologist,
      status: data.psychologist_status,
      error: data.psychologist_error,
      technicalAnalysis: data.technical_analysis,
    });
    historyEntries = addHistoryEntry(historyEntries, {
      text,
      detective,
      psychologist: normalizePsychologist(
        data.psychologist,
        data.psychologist_status,
        data.psychologist_error,
      ),
      technicalAnalysis: data.technical_analysis,
    });
    persistHistory();
    elements.status.textContent = data.cache?.hit
      ? 'Đã dùng kết quả trùng khớp trong bộ nhớ đệm; không gọi AI lại.'
      : 'Đã kiểm tra xong tin nhắn.';
  } catch (error) {
    elements.status.textContent = '';
    showError(error instanceof ApiError ? error.message : 'Có lỗi không xác định. Vui lòng thử lại.');
  } finally {
    activeController = null;
    setLoading(false);
  }
}

function openHistoryEntry(id) {
  const entry = historyEntries.find((item) => item.id === id);
  if (!entry) return;
  stopSpeech();
  elements.textInput.value = normalizeNfc(entry.text);
  showResult(entry.text, entry.detective, {
    psychologist: entry.psychologist?.message ? { message: entry.psychologist.message } : null,
    status: entry.psychologist?.status || 'not_needed',
    error: entry.psychologist?.error || '',
    technicalAnalysis: entry.technicalAnalysis,
  });
  elements.status.textContent = 'Đang xem lại kết quả đã lưu trên thiết bị. Không gọi AI.';
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
    if (transcript) {
      elements.textInput.value = normalizeNfc(appendTranscript(elements.textInput.value, transcript));
    }
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
elements.cancelCheckBtn.addEventListener('click', () => {
  if (activeController) activeController.abort();
});
elements.clearBtn.addEventListener('click', clearCurrent);
elements.textInput.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') onCheck();
});
elements.textInput.addEventListener('change', () => {
  elements.textInput.value = normalizeNfc(elements.textInput.value);
});

document.querySelectorAll('[data-sample]').forEach((button) => {
  button.addEventListener('click', () => {
    elements.textInput.value = normalizeNfc(samples[button.dataset.sample] || '');
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

elements.libraryToggleBtn.addEventListener('click', () => {
  setLibraryCollapsed(elements.libraryPanel.dataset.collapsed !== 'true');
});

elements.libraryFilters.addEventListener('click', (event) => {
  const button = event.target.closest('[data-library-group]');
  if (!button) return;
  const group = button.dataset.libraryGroup;
  if (group === 'all') {
    history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
  } else {
    window.location.hash = group;
  }
  renderLibrary(group);
});
window.addEventListener('hashchange', () => {
  renderLibrary(libraryGroupFromHash(
    window.location.hash,
    libraryData.groups.map((item) => item.key),
  ));
});

renderHistory();
setupSpeech();
setupLibrary();
