// Logic giao diện trang kiểm tra (/). Thư viện đã tách ra library.js; trang này
// KHÔNG fetch /api/scam-library và không phụ thuộc DOM thư viện.
// Chuẩn hoá NFC ở mọi boundary để tránh browser render Unicode tổ hợp sai.
import { check, rescue, fetchShareQrSvg, ApiError } from './api.js?v=stage5-tabs-v11';
import { renderHighlightedText } from './highlight-excerpts.js';
import {
  addHistoryEntry,
  clearHistory,
  deleteHistoryEntry,
  loadHistory,
  saveHistory,
} from './history.js';
import { wirePreferences } from './preferences.js';
import { buildRescuePayload, normalizeRescue, SITUATIONS as RESCUE_SITUATIONS } from './rescue-model.js';
import { normalizeDetective, RISK_META, offersRescueGuidance, offersShareCard } from './result-model.js?v=stage5-tabs-v11';
import {
  buildShareCardModel,
  decodeQrModules,
  drawShareCard,
  safeFileName,
} from './share-card.js?v=stage5-tabs-v11';
import { normalizePsychologist } from './stage3-model.js';
import { normalizeTechnicalAnalysis } from './stage4-model.js';
import { normalizeNfc } from './unicode.js';
import { materialIcon } from './icons.js';
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

const RISK_ICON_NAMES = Object.freeze({
  an_toan: 'gpp_good',
  nghi_ngo: 'warning',
  nguy_hiem: 'priority_high',
  khong_lien_quan: 'info',
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
};

let historyEntries = loadHistory(window.localStorage);
let recognition = null;
let isListening = false;
let activeController = null;
let progressTimers = [];

// Stage 5: luồng ứng cứu một chạm + ảnh chia sẻ.
let currentCheck = null;
let rescueController = null;
let rescueToken = 0;
let shareController = null;
let shareToken = 0;

const RESCUE_CHOICES = Object.freeze([
  { situation: 'chua_lam_gi', label: RESCUE_SITUATIONS.chua_lam_gi },
  { situation: 'da_bam_link', label: RESCUE_SITUATIONS.da_bam_link },
  { situation: 'da_chuyen_tien', label: RESCUE_SITUATIONS.da_chuyen_tien },
  { situation: 'da_cung_cap_otp', label: RESCUE_SITUATIONS.da_cung_cap_otp },
]);

function createElement(tag, { className = '', text = '', attributes = {} } = {}) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
  return element;
}

function scrollToBlock(element, { focus = false } = {}) {
  if (!element) return false;
  window.requestAnimationFrame(() => {
    if (!element.isConnected) return;
    element.scrollIntoView({ block: 'start' });
    if (focus && typeof element.focus === 'function') element.focus({ preventScroll: true });
  });
  return true;
}

function setupHeroDoubleTap() {
  const hero = document.querySelector('.hero');
  const inputCard = document.querySelector('.input-card');
  if (!hero || !inputCard) return;

  let pointerStart = null;
  let previousTap = null;
  let lastShortcutAt = 0;
  const goToInput = () => {
    const now = Date.now();
    if (now - lastShortcutAt < 500) return;
    lastShortcutAt = now;
    scrollToBlock(inputCard);
    window.requestAnimationFrame(() => elements.textInput.focus({ preventScroll: true }));
    elements.status.textContent = 'Đã đưa bác tới ô nhập tin nhắn.';
  };

  hero.addEventListener('dblclick', goToInput);
  hero.addEventListener('pointerdown', (event) => {
    if (event.pointerType !== 'touch') return;
    pointerStart = { id: event.pointerId, x: event.clientX, y: event.clientY };
  });
  hero.addEventListener('pointercancel', () => { pointerStart = null; });
  hero.addEventListener('pointerup', (event) => {
    if (event.pointerType !== 'touch' || !pointerStart || pointerStart.id !== event.pointerId) return;
    const moved = Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y);
    pointerStart = null;
    if (moved > 16) { previousTap = null; return; }
    const tap = { at: Date.now(), x: event.clientX, y: event.clientY };
    if (previousTap
      && tap.at - previousTap.at <= 360
      && Math.hypot(tap.x - previousTap.x, tap.y - previousTap.y) <= 32) {
      previousTap = null;
      goToInput();
      return;
    }
    previousTap = tap;
  });
}

function riskIcon(riskLevel) {
  return materialIcon(RISK_ICON_NAMES[riskLevel] || 'warning', { className: 'risk-icon' });
}

function deleteIcon() {
  return materialIcon('delete', { className: 'icon-glyph' });
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
  card.append(riskIcon(detective.risk_level), copy);
  container.append(card);
}

function createResultDisclosure(title, className = '') {
  const details = createElement('details', {
    className: `result-section result-disclosure rescue-collapsible ${className}`.trim(),
    attributes: { open: '' },
  });
  const summary = createElement('summary', { className: 'result-disclosure-summary' });
  summary.append(
    createElement('span', { className: 'result-disclosure-title', text: title }),
    materialIcon('expand_more', { className: 'result-disclosure-arrow' }),
  );
  const content = createElement('div', { className: 'result-disclosure-content' });
  details.append(summary, content);
  return { details, content };
}

function appendSourceMessage(container, text, detective) {
  const { details, content } = createResultDisclosure('Đoạn đáng chú ý trong tin gốc');
  const source = createElement('p', { className: 'source-message' });
  const excerpts = detective.red_flags.map((flag) => flag.excerpt).filter(Boolean);
  renderHighlightedText(source, text, excerpts);
  content.append(source);
  container.append(details);
}

function appendTechnicalAnalysis(container, rawTechnical) {
  const technical = normalizeTechnicalAnalysis(rawTechnical);
  if (!technical.links.length && !technical.ruleSignals.length) return;
  const section = createElement('details', { className: 'result-section technical-analysis' });
  const summary = createElement('summary', {
    className: 'technical-summary',
  });
  summary.append(
    materialIcon('rule', { className: 'technical-summary-icon' }),
    createElement('span', { text: 'Xem kiểm tra kỹ thuật' }),
  );
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
  const { details, content } = createResultDisclosure('Dấu hiệu cần chú ý');
  if (!detective.red_flags.length) {
    content.append(createElement('p', {
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
    content.append(list);
  }
  container.append(details);
}

function appendActions(container, detective) {
  if (!detective.actions.length) return;
  const section = createElement('section', { className: 'result-section immediate-actions' });
  section.append(createElement('h3', { text: 'Ba việc bác nên làm ngay' }));
  const list = createElement('ol', { className: 'action-list numbered-steps' });
  detective.actions.forEach((action) => list.append(createElement('li', { text: action })));
  section.append(list);
  container.append(section);
}

function appendPsychologist(container, rawPsychologist, status, error) {
  const psychologist = normalizePsychologist(rawPsychologist, status, error);
  if (psychologist.status === 'not_needed') return;
  const { details, content } = createResultDisclosure('Cô tâm lý giải thích', 'psychologist-card');
  const summary = details.querySelector('.result-disclosure-summary');
  summary.prepend(materialIcon('verified', { className: 'eyebrow-icon' }));
  content.prepend(createElement('p', { className: 'section-eyebrow', text: 'Góc nhìn thứ hai' }));
  if (psychologist.status === 'complete') {
    content.append(createElement('p', { className: 'psychologist-message', text: psychologist.message }));
  } else {
    content.append(createElement('p', {
      className: 'psychologist-unavailable',
      text: psychologist.error || 'Cô tâm lý chưa thể giải thích thêm; kết quả Thám tử vẫn đầy đủ.',
    }));
  }
  container.append(details);
}

function showResult(text, rawDetective, psychologistOptions = {}, { focus = true } = {}) {
  const detective = normalizeDetective(rawDetective);
  abortRescueAndShare();
  currentCheck = { text, detective };
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
  appendRescueFlow(elements.result, currentCheck);
  appendTechnicalAnalysis(elements.result, psychologistOptions.technicalAnalysis);
  appendShareSection(elements.result, currentCheck);
  elements.result.hidden = false;
  elements.error.hidden = true;
  if (focus) elements.result.focus({ preventScroll: true });
  return detective;
}

function abortRescueAndShare() {
  if (rescueController) { rescueController.abort(); rescueController = null; }
  if (shareController) { shareController.abort(); shareController = null; }
  rescueToken += 1;
  shareToken += 1;
}

// ---- Rescue flow (Stage 5) ---------------------------------------------

function appendRescueFlow(container, checkContext) {
  if (!offersRescueGuidance(checkContext.detective.risk_level)) return;

  // Prominent "Tiếp tục" gate after the Detective/Psychologist explanation (#5):
  // the rescue question stays hidden until this action, then is revealed,
  // scrolled into view (sticky-header-safe) and focused.
  const gate = createElement('section', {
    className: 'continue-gate',
    attributes: { 'aria-labelledby': 'continueGateTitle' },
  });
  const gateTitle = createElement('h3', {
    className: 'continue-gate-title',
    attributes: { id: 'continueGateTitle' },
  });
  gateTitle.append(
    materialIcon('support_agent', { className: 'eyebrow-icon' }),
    document.createTextNode('Đã đọc xong phần giải thích?'),
  );
  gate.append(
    gateTitle,
    createElement('p', {
      className: 'continue-gate-text',
      text: 'Chọn tiếp tục để nói rõ tình huống hiện tại — kể cả khi bác chưa làm gì — rồi xem hướng dẫn từng bước và số liên hệ đã đối chiếu.',
    }),
  );
  const continueBtn = createElement('button', {
    className: 'button-primary continue-btn',
    attributes: { type: 'button', 'data-action': 'reveal-rescue' },
  });
  continueBtn.append(
    document.createTextNode('Tiếp tục — chọn tình huống'),
    materialIcon('arrow_forward', { className: 'icon-glyph' }),
  );
  gate.append(continueBtn);
  container.append(gate);

  const rescue = buildRescueSection(checkContext);
  rescue.hidden = true;
  container.append(rescue);

  continueBtn.addEventListener('click', () => revealRescue(gate, rescue));
}

function buildRescueSection(checkContext) {
  const section = createElement('section', {
    className: 'result-section rescue-section',
    attributes: { 'aria-labelledby': 'rescueTitle', tabindex: '-1', 'data-revealed': 'false' },
  });
  // Decision box (#4): question + four equal-track choices in a high-contrast
  // deep-forest panel inspired by the reference's final yes/no panel.
  const decision = createElement('div', { className: 'rescue-decision' });
  decision.append(createElement('p', { className: 'rescue-decision-eyebrow', text: 'Bước ứng cứu' }));
  const heading = createElement('h3', { attributes: { id: 'rescueTitle' } });
  heading.append(materialIcon('support_agent', { className: 'eyebrow-icon' }), document.createTextNode('Bác đã làm gì rồi?'));
  decision.append(
    heading,
    createElement('p', {
      className: 'rescue-intro',
      text: 'Chọn đúng một tình huống — ScamCheck sẽ đưa ra từng bước tiếp theo và số liên hệ đã đối chiếu. Đây là hướng dẫn giáo dục, không thay thế ngân hàng hay cơ quan chức năng.',
    }),
  );
  const choices = createElement('div', {
    className: 'rescue-choices',
    attributes: { role: 'group', 'aria-label': 'Chọn tình huống bác đã gặp' },
  });
  RESCUE_CHOICES.forEach(({ situation, label }) => {
    choices.append(createElement('button', {
      className: 'rescue-choice',
      text: label,
      attributes: { type: 'button', 'data-rescue': situation, 'aria-pressed': 'false' },
    }));
  });
  decision.append(choices);
  const status = createElement('p', {
    className: 'rescue-status status',
    attributes: { role: 'status', 'aria-live': 'polite' },
  });
  const output = createElement('div', { className: 'rescue-output' });
  section.append(decision, status, output);
  choices.addEventListener('click', (event) => {
    const button = event.target.closest('[data-rescue]');
    if (!button) return;
    onRescueChoice(button.dataset.rescue, { choices, output, status, context: checkContext });
  });
  return section;
}

function revealRescue(gate, rescue) {
  const resultPanel = gate.parentElement;
  resultPanel?.querySelectorAll('.rescue-collapsible[open]').forEach((details) => {
    details.removeAttribute('open');
  });
  gate.hidden = true;
  rescue.hidden = false;
  rescue.setAttribute('data-revealed', 'true');
  if (elements.status) {
    elements.status.textContent = 'Đã thu gọn phần giải thích. Chọn đúng một tình huống ứng cứu bên dưới.';
  }
  // scroll-behavior is driven by CSS (auto under prefers-reduced-motion);
  // scroll-margin-top on the section clears the sticky app bar.
  rescue.scrollIntoView({ block: 'start' });
  rescue.focus({ preventScroll: true });
}

function setRescueBusy(choices, output, status, busy, selectedSituation, locked = false) {
  choices.dataset.state = busy ? 'busy' : (locked ? 'locked' : 'idle');
  choices.querySelectorAll('[data-rescue]').forEach((button) => {
    button.disabled = busy || locked;
    button.setAttribute('aria-pressed', String(!busy && button.dataset.rescue === selectedSituation));
  });
  if (busy) {
    const loading = createElement('span', { className: 'rescue-loading' });
    loading.append(
      createElement('span', { className: 'spinner', attributes: { 'aria-hidden': 'true' } }),
      createElement('span', { text: 'Đang soạn từng bước ứng cứu…' }),
    );
    output.replaceChildren(loading);
    status.textContent = 'Đang chuẩn bị từng bước ứng cứu…';
  }
}

async function onRescueChoice(situation, scope) {
  rescueToken += 1;
  const token = rescueToken;
  if (rescueController) rescueController.abort();
  rescueController = new AbortController();
  const payload = buildRescuePayload(situation, {
    messageText: scope.context.text,
    riskLevel: scope.context.detective.risk_level,
    redFlags: scope.context.detective.red_flags,
  });
  if (!payload) return;
  setRescueBusy(scope.choices, scope.output, scope.status, true, situation);
  try {
    const data = await rescue(payload, { signal: rescueController.signal });
    if (token !== rescueToken) return;
    const rescueCard = renderRescueResult(scope.output, scope.status, normalizeRescue(data), situation);
    setRescueBusy(scope.choices, scope.output, scope.status, false, situation, true);
    scrollToBlock(rescueCard, { focus: true });
  } catch (error) {
    if (token !== rescueToken) return;
    if (error?.code === 'cancelled' || error?.name === 'AbortError') return;
    renderRescueError(scope.output, scope.status, error, () => onRescueChoice(situation, scope));
    setRescueBusy(scope.choices, scope.output, scope.status, false, situation);
  } finally {
    if (token === rescueToken) rescueController = null;
  }
}

function renderRescueResult(output, status, rescue, selectedSituation) {
  output.replaceChildren();
  const card = createElement('div', {
    className: 'rescue-card',
    attributes: { tabindex: '-1', role: 'group', 'aria-label': 'Các bước ứng cứu' },
  });
  if (rescue.situationLabel) {
    card.append(createElement('p', { className: 'rescue-situation', text: `Tình huống: ${rescue.situationLabel}` }));
  }
  if (rescue.praise) {
    card.append(createElement('p', { className: 'rescue-praise', text: rescue.praise }));
  }
  if (rescue.rescue.headline) {
    card.append(createElement('h4', { className: 'rescue-headline', text: rescue.rescue.headline }));
  }
  if (rescue.rescue.reassurance) {
    card.append(createElement('p', { className: 'rescue-reassurance', text: rescue.rescue.reassurance }));
  }
  if (rescue.rescueStatus === 'guarded_fallback') {
    card.append(createElement('p', {
      className: 'rescue-fallback-note',
      text: rescue.rescueError || 'Người ứng cứu tự động đang dùng quy trình an toàn có sẵn.',
    }));
  }
  if (rescue.rescue.steps.length) {
    const list = createElement('ol', { className: 'rescue-steps numbered-steps' });
    rescue.rescue.steps.forEach((step) => list.append(createRescueStep(step)));
    card.append(list);
  }
  if (rescue.rescue.closing) {
    card.append(createElement('p', { className: 'rescue-closing', text: rescue.rescue.closing }));
  }
  if (rescue.matchedInstitutions.length) {
    const wrap = createElement('p', { className: 'rescue-matched' });
    wrap.append(document.createTextNode('Có vẻ nhắc đến '));
    rescue.matchedInstitutions.forEach((name, index) => {
      if (index > 0) wrap.append(document.createTextNode(', '));
      wrap.append(createElement('strong', { text: name }));
    });
    wrap.append(document.createTextNode('.'));
    card.append(wrap);
  }
  if (rescue.safetyNotice) {
    card.append(createElement('p', { className: 'rescue-safety', text: rescue.safetyNotice }));
  }
  output.append(card);
  status.textContent = rescue.rescueStatus === 'not_needed'
    ? 'Đã có kế hoạch phòng ngừa.'
    : 'Đã sẵn sàng từng bước ứng cứu.';
  void selectedSituation;
  return card;
}

function createRescueStep(step) {
  const item = createElement('li', { className: 'rescue-step' });
  const head = createElement('p', { className: 'rescue-step-head' });
  head.append(
    createElement('span', {
      className: 'rescue-step-number',
      attributes: { 'aria-hidden': 'true' },
      text: String(step.step),
    }),
    createElement('span', { className: 'rescue-step-action', text: step.action }),
  );
  item.append(head);
  if (step.detail) {
    item.append(createElement('p', { className: 'rescue-step-detail', text: step.detail }));
  }
  if (step.hotlines.length) {
    const contacts = createElement('ul', { className: 'rescue-hotlines' });
    step.hotlines.forEach((hotline) => contacts.append(createRescueHotline(hotline)));
    item.append(contacts);
  }
  return item;
}

function createRescueHotline(hotline) {
  const item = createElement('li', { className: 'rescue-hotline' });
  const lead = createElement('span', { className: 'rescue-hotline-lead' });
  lead.append(createElement('span', { className: 'rescue-hotline-name', text: hotline.name }));
  if (hotline.contactHref) {
    const link = createElement('a', {
      className: 'rescue-hotline-phone',
      text: hotline.channel === 'sms' ? `Nhắn ${hotline.phone}` : hotline.phone,
      attributes: { href: hotline.contactHref },
    });
    link.prepend(materialIcon(hotline.channel === 'sms' ? 'sms' : 'call', { className: 'hotline-icon' }));
    lead.append(document.createTextNode(' '), link);
  } else if (hotline.phone) {
    lead.append(document.createTextNode(` ${hotline.phone}`));
  }
  item.append(lead);
  const metaParts = [];
  if (hotline.sourceLabel) metaParts.push(hotline.sourceLabel);
  if (hotline.reviewedAt) metaParts.push(`đối chiếu ${hotline.reviewedAt}`);
  if (metaParts.length) {
    item.append(document.createTextNode(' — '), createElement('span', { className: 'rescue-hotline-meta', text: metaParts.join(' · ') }));
  }
  if (hotline.emergencyOnly) {
    item.append(createElement('span', { className: 'rescue-emergency', text: 'Chỉ gọi khi khẩn cấp.' }));
  }
  return item;
}

function renderRescueError(output, status, error, retry) {
  output.replaceChildren();
  const panel = createElement('div', { className: 'error-panel', attributes: { role: 'alert' } });
  panel.append(createElement('p', {
    text: error instanceof ApiError ? error.message : 'Chưa tải được quy trình ứng cứu. Vui lòng thử lại.',
  }));
  const retryButton = createElement('button', {
    className: 'button-secondary',
  });
  retryButton.append(materialIcon('refresh', { className: 'icon-glyph' }), document.createTextNode('Thử lại'));
  retryButton.addEventListener('click', retry);
  panel.append(retryButton);
  output.append(panel);
  status.textContent = 'Quy trình ứng cứu chưa tải được.';
}

// ---- Share card (Stage 5) -----------------------------------------------

function appendShareSection(container, checkContext) {
  if (!offersShareCard(checkContext.detective.risk_level)) return;
  const isSafe = checkContext.detective.risk_level === 'an_toan';
  const section = createElement('section', {
    className: 'result-section share-section',
    attributes: { 'aria-labelledby': 'shareTitle' },
  });
  const heading = createElement('h3', {
    attributes: { id: 'shareTitle' },
  });
  heading.append(
    materialIcon(isSafe ? 'share' : 'campaign', { className: 'eyebrow-icon' }),
    document.createTextNode(isSafe ? 'Gửi kết quả cho người thân' : 'Gửi cảnh báo cho người thân'),
  );
  section.append(
    heading,
    createElement('p', {
      className: 'share-intro',
      text: 'Tạo một ảnh nhỏ chỉ có mức rủi ro, vài dấu hiệu chính và mã QR dẫn về ScamCheck — không chứa toàn văn tin nhắn, số tài khoản hay thông tin cá nhân.',
    }),
  );
  const canvas = createElement('canvas', {
    className: 'share-canvas',
    attributes: { role: 'img', 'aria-label': 'Ảnh cảnh báo đang chuẩn bị.' },
  });
  const preview = createElement('div', { className: 'share-preview' });
  preview.hidden = true;
  preview.append(canvas);
  const status = createElement('p', {
    className: 'share-status status',
    attributes: { role: 'status', 'aria-live': 'polite' },
    text: 'Ảnh chưa được tạo; toàn văn tin nhắn sẽ không xuất hiện trong ảnh.',
  });
  const errorBox = createElement('div', { className: 'error-panel share-error', attributes: { role: 'alert' } });
  errorBox.hidden = true;
  const generateBtn = createElement('button', { className: 'button-secondary', attributes: { type: 'button' } });
  generateBtn.append(materialIcon('share', { className: 'icon-glyph' }), document.createTextNode('Tạo ảnh cảnh báo'));
  const shareBtn = createElement('button', {
    className: 'button-secondary',
    attributes: { type: 'button', disabled: '' },
  });
  shareBtn.append(materialIcon('share', { className: 'icon-glyph' }), document.createTextNode('Chia sẻ ảnh'));
  const saveBtn = createElement('button', {
    className: 'button-secondary',
    attributes: { type: 'button', disabled: '' },
  });
  saveBtn.append(materialIcon('download', { className: 'icon-glyph' }), document.createTextNode('Lưu ảnh'));
  const actions = createElement('div', { className: 'share-actions' });
  actions.hidden = true;
  actions.append(shareBtn, saveBtn);
  section.append(generateBtn, preview, actions, status, errorBox);
  container.append(section);

  const ctx = {
    canvas,
    preview,
    actions,
    generateBtn,
    status,
    errorBox,
    shareBtn,
    saveBtn,
    checkContext,
    state: {
      wired: false,
      model: null,
      fileName: safeFileName(`scamcheck-${checkContext.detective.risk_level}`),
    },
  };
  generateBtn.addEventListener('click', () => mountShareCard(ctx));
  shareBtn.addEventListener('click', () => onShareImage(ctx, 'share'));
  saveBtn.addEventListener('click', () => onShareImage(ctx, 'save'));
}

async function mountShareCard(ctx) {
  shareToken += 1;
  const token = shareToken;
  if (shareController) shareController.abort();
  shareController = new AbortController();
  ctx.errorBox.hidden = true;
  ctx.generateBtn.disabled = true;
  ctx.preview.hidden = false;
  ctx.canvas.hidden = false;
  ctx.actions.hidden = true;
  ctx.shareBtn.disabled = true;
  ctx.saveBtn.disabled = true;
  ctx.status.textContent = 'Đang tải mã QR và vẽ ảnh cảnh báo…';
  try {
    const svgText = await fetchShareQrSvg({ signal: shareController.signal });
    if (token !== shareToken) return;
    const qrData = decodeQrModules(svgText);
    const url = extractQrUrl(svgText);
    const model = buildShareCardModel(ctx.checkContext.detective, { url });
    ctx.state.model = model;
    drawShareCard(ctx.canvas, model, qrData);
    ctx.canvas.setAttribute('aria-label', shareCanvasLabel(model));
    ctx.status.textContent = 'Ảnh đã sẵn sàng. Chọn “Chia sẻ ảnh” hoặc “Lưu ảnh”.';
    ctx.generateBtn.hidden = true;
    ctx.actions.hidden = false;
    ctx.shareBtn.disabled = false;
    ctx.saveBtn.disabled = false;
  } catch (error) {
    if (token !== shareToken) return;
    if (error?.code === 'cancelled' || error?.name === 'AbortError') return;
    renderShareError(ctx, error);
  } finally {
    if (token === shareToken) shareController = null;
  }
}

function renderShareError(ctx, error) {
  ctx.preview.hidden = true;
  ctx.canvas.hidden = true;
  ctx.actions.hidden = true;
  ctx.generateBtn.hidden = false;
  ctx.generateBtn.disabled = false;
  ctx.shareBtn.disabled = true;
  ctx.saveBtn.disabled = true;
  ctx.status.textContent = 'Chưa tạo được ảnh cảnh báo.';
  ctx.errorBox.replaceChildren(createElement('p', {
    text: error instanceof ApiError ? error.message : 'Không tạo được ảnh chia sẻ. Vui lòng thử lại.',
  }));
  const retry = createElement('button', { className: 'button-secondary', attributes: { type: 'button' } });
  retry.append(materialIcon('refresh', { className: 'icon-glyph' }), document.createTextNode('Tạo lại ảnh'));
  retry.addEventListener('click', () => mountShareCard(ctx));
  ctx.errorBox.append(retry);
  ctx.errorBox.hidden = false;
}

function shareCanvasLabel(model) {
  const signsText = model.signs.length ? `${model.signs.length} dấu hiệu chính.` : '';
  return `Ảnh cảnh báo ScamCheck: mức ${model.riskLabel.toLowerCase()}. ${signsText} Có mã QR dẫn về ScamCheck để tự kiểm tra.`.replace(/\s+/g, ' ').trim();
}

function extractQrUrl(svgText) {
  try {
    const doc = new DOMParser().parseFromString(String(svgText || ''), 'image/svg+xml');
    const label = doc.documentElement.getAttribute('aria-label') || '';
    const match = /https?:\/\/\S+/.exec(label);
    if (match) return match[0].replace(/[.,)]+$/, '');
  } catch {
    /* bỏ qua */
  }
  return typeof window !== 'undefined' && window.location ? window.location.origin : '';
}

async function onShareImage(ctx, mode) {
  if (!ctx.state.model || !ctx.canvas || ctx.canvas.width === 0 || ctx.canvas.height === 0) {
    ctx.status.textContent = 'Chưa có ảnh. Hãy bấm “Tạo ảnh cảnh báo” trước, rồi mới chia sẻ hoặc lưu.';
    return;
  }
  ctx.status.textContent = mode === 'share' ? 'Đang mở chia sẻ…' : 'Đang chuẩn bị ảnh…';
  let objectUrl = null;
  let link = null;
  try {
    const blob = await canvasToBlob(ctx.canvas);
    const file = typeof File === 'function'
      ? new File([blob], ctx.state.fileName, { type: 'image/png' })
      : null;
    let canShareFile = false;
    if (mode === 'share' && file && typeof navigator.share === 'function'
      && typeof navigator.canShare === 'function') {
      try { canShareFile = navigator.canShare({ files: [file] }); } catch { canShareFile = false; }
    }
    if (canShareFile) {
      await navigator.share({ files: [file], title: 'ScamCheck', text: ctx.state.model.riskLabel });
      ctx.status.textContent = 'Đã chia sẻ ảnh.';
      return;
    }
    objectUrl = URL.createObjectURL(blob);
    const isIos = /iPad|iPhone|iPod/.test(navigator.userAgent)
      || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    if (mode === 'share' && isIos) {
      window.open(objectUrl, '_blank', 'noopener');
      ctx.status.textContent = 'Đã mở ảnh ở tab mới. Chạm giữ ảnh rồi chọn “Lưu vào Ảnh”.';
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
      objectUrl = null;
      return;
    }
    link = document.createElement('a');
    link.rel = 'noopener';
    link.href = objectUrl;
    link.download = ctx.state.fileName;
    document.body.append(link);
    link.click();
    ctx.status.textContent = 'Đã tải ảnh về máy.';
    // Defer removal + revoke: some engines cancel the download when the anchor
    // is detached synchronously right after click().
    window.setTimeout(() => {
      if (link && link.parentNode) link.remove();
      if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
    }, 1500);
  } catch (error) {
    if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
    if (link && link.parentNode) link.remove();
    ctx.status.textContent = error && error.name === 'AbortError'
      ? 'Đã huỷ chia sẻ.'
      : 'Chưa chia sẻ được ảnh. Vui lòng thử lại.';
  }
}

function canvasToBlob(canvas) {
  return new Promise((resolve, reject) => {
    if (typeof canvas.toBlob === 'function') {
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('blob-empty'))), 'image/png');
      return;
    }
    if (typeof canvas.toDataURL === 'function') {
      try { resolve(dataUrlToBlob(canvas.toDataURL('image/png'))); }
      catch (error) { reject(error); }
      return;
    }
    reject(new Error('canvas-unsupported'));
  });
}

function dataUrlToBlob(dataUrl) {
  const [head, body] = String(dataUrl).split(',');
  const mime = /:(.*?);/.exec(head)?.[1] || 'image/png';
  const binary = atob(body);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: mime });
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
      createElement('span', {
        className: `history-risk chip-${detective.risk_level}`,
        text: RISK_META[detective.risk_level].label,
      }),
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

function clearCurrent() {
  stopSpeech();
  if (activeController) activeController.abort();
  abortRescueAndShare();
  currentCheck = null;
  elements.textInput.value = '';
  elements.result.hidden = true;
  elements.error.hidden = true;
  elements.loadingPanel.hidden = true;
  elements.status.textContent = '';
  elements.textInput.focus();
}

async function onCheck() {
  let verdictCard = null;
  if (activeController) {
    elements.status.textContent = 'Lượt kiểm tra hiện tại vẫn đang chạy.';
    return;
  }
  abortRescueAndShare();
  currentCheck = null;
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
    verdictCard = elements.result.querySelector('.risk-card');
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
    if (verdictCard) scrollToBlock(verdictCard);
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

renderHistory();
setupSpeech();
setupHeroDoubleTap();

const displayPrefs = document.getElementById('displayPrefs');
if (displayPrefs) wirePreferences({ root: displayPrefs });
