import { ApiError, getQuiz } from './api.js';
import { wirePreferences } from './preferences.js';
import { normalizeQuiz, quizGuidance, scoreQuiz } from './stage4-model.js';
import { materialIcon } from './icons.js';

const elements = {
  status: document.getElementById('practiceStatus'),
  error: document.getElementById('practiceError'),
  card: document.getElementById('questionCard'),
  summary: document.getElementById('quizSummary'),
};

let questions = [];
let currentIndex = 0;
let answers = {};
let isLoadingQuiz = false;
let loadAttempts = 0;

function createElement(tag, { className = '', text = '', attributes = {} } = {}) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

/** Nút có icon (Material) đặt trước nhãn; nhãn là text node an toàn. */
function labeledButton(tag, className, iconName, labelText, attributes = {}) {
  const element = createElement(tag, { className, attributes });
  element.append(materialIcon(iconName, { className: 'icon-glyph' }), document.createTextNode(labelText));
  return element;
}

function showSummary() {
  const score = scoreQuiz(answers, questions);
  elements.card.hidden = true;
  elements.summary.replaceChildren(
    createElement('p', { className: 'section-eyebrow', text: 'Hoàn thành 10 câu' }),
    createElement('h2', { text: `Bác trả lời đúng ${score}/${questions.length} câu` }),
    createElement('p', { className: 'summary-score', text: quizGuidance(score, questions.length) }),
  );
  const restart = labeledButton('button', 'button-primary', 'refresh', 'Luyện lại từ đầu', { type: 'button' });
  restart.addEventListener('click', () => {
    currentIndex = 0;
    answers = {};
    elements.summary.hidden = true;
    renderQuestion();
  });
  const home = labeledButton('a', 'button-link', 'fact_check', 'Kiểm tra một tin thật', { href: '/' });
  const actions = createElement('div', { className: 'primary-actions' });
  actions.append(restart, home);
  elements.summary.append(actions);
  elements.summary.hidden = false;
  elements.status.textContent = `Đã hoàn thành. Kết quả ${score} trên ${questions.length} câu.`;
  elements.summary.focus({ preventScroll: true });
}

function answerQuestion(choice) {
  const question = questions[currentIndex];
  if (Object.hasOwn(answers, question.id)) return;
  answers = { ...answers, [question.id]: choice };
  const correct = choice === question.is_scam;
  elements.card.querySelectorAll('[data-answer]').forEach((button) => {
    button.disabled = true;
    button.setAttribute('aria-pressed', String(button.dataset.answer === String(choice)));
  });
  const feedback = createElement('div', {
    className: `quiz-feedback ${correct ? 'correct' : 'incorrect'}`,
    attributes: { role: 'status' },
  });
  const heading = createElement('h3', { className: 'feedback-title' });
  heading.append(materialIcon(correct ? 'check_circle' : 'info', { className: 'eyebrow-icon' }), document.createTextNode(correct ? 'Bác chọn đúng' : 'Chưa đúng — mình xem lại dấu hiệu nhé'));
  feedback.append(
    heading,
    createElement('p', { text: question.explanation }),
    createElement('p', { className: 'quiz-tip', text: `Mẹo: ${question.tip}` }),
  );
  const next = labeledButton('button', 'button-primary', 'arrow_forward', currentIndex === questions.length - 1 ? 'Xem tổng kết' : 'Câu tiếp theo', { type: 'button', 'data-quiz-next': 'true' });
  next.addEventListener('click', () => {
    currentIndex += 1;
    if (currentIndex >= questions.length) showSummary();
    else renderQuestion();
  });
  feedback.append(next);
  elements.card.append(feedback);
  elements.status.textContent = correct ? 'Câu trả lời đúng.' : 'Câu trả lời chưa đúng; phần giải thích đã hiện.';
  feedback.focus?.();
  next.focus({ preventScroll: true });
}

function renderQuestion() {
  const question = questions[currentIndex];
  const progressRow = createElement('div', { className: 'quiz-progress-row' });
  progressRow.append(
    createElement('p', { className: 'quiz-progress', text: `Câu ${currentIndex + 1} / ${questions.length}` }),
    createElement('progress', {
      className: 'quiz-progress-bar',
      attributes: {
        value: String(currentIndex + 1),
        max: String(questions.length),
        'aria-label': `Tiến độ: câu ${currentIndex + 1} trên ${questions.length}`,
      },
    }),
  );
  elements.card.replaceChildren(
    progressRow,
    createElement('p', { className: 'section-eyebrow', text: question.category }),
    createElement('h2', { text: 'Tin nhắn này có dấu hiệu lừa đảo không?' }),
    createElement('blockquote', { className: 'quiz-message', text: question.text }),
  );
  const choices = createElement('div', { className: 'quiz-choices', attributes: { role: 'group', 'aria-label': 'Chọn đáp án' } });
  [
    [true, 'Có dấu hiệu lừa đảo', 'warning'],
    [false, 'Có vẻ an toàn', 'check_circle'],
  ].forEach(([value, label, iconName]) => {
    const button = labeledButton('button', value ? 'button-danger-choice' : 'button-safe-choice', iconName, label, { type: 'button', 'data-answer': String(value), 'aria-pressed': 'false' });
    button.addEventListener('click', () => answerQuestion(value));
    choices.append(button);
  });
  elements.card.append(choices);
  elements.card.hidden = false;
  elements.status.textContent = `Đang ở câu ${currentIndex + 1} trên ${questions.length}.`;
  elements.card.focus({ preventScroll: true });
}

function showLoadError(error) {
  const detail = error instanceof ApiError
    ? 'Máy chủ chưa gửi được bộ câu hỏi.'
    : 'Dữ liệu câu hỏi chưa sẵn sàng.';
  const attemptText = loadAttempts > 1
    ? `Lần thử ${loadAttempts} vẫn chưa thành công.`
    : 'Lượt tải đầu tiên chưa thành công.';
  const retry = labeledButton('button', 'button-primary practice-retry', 'refresh', 'Thử tải lại 10 câu', { type: 'button' });
  retry.addEventListener('click', () => {
    // Error panel can render before the prior promise reaches `finally`.
    // Reset the guard so an immediate retry is never swallowed.
    isLoadingQuiz = false;
    setup();
  });
  const recovery = createElement('ol', { className: 'practice-recovery' });
  ['Kiểm tra kết nối mạng.', 'Bấm “Thử tải lại 10 câu”.', 'Nếu vẫn lỗi, dùng nút “Về trang kiểm tra”.']
    .forEach((step) => recovery.append(createElement('li', { text: step })));
  elements.error.replaceChildren(
    createElement('p', { text: `${attemptText} ${detail}` }),
    recovery,
    retry,
  );
  elements.error.hidden = false;
  elements.error.focus({ preventScroll: true });
}

async function setup() {
  if (isLoadingQuiz) return;
  isLoadingQuiz = true;
  loadAttempts += 1;
  elements.error.hidden = true;
  elements.status.textContent = loadAttempts > 1
    ? `Đang thử tải lại 10 câu — lần ${loadAttempts}…`
    : 'Đang tải 10 câu luyện tập…';
  try {
    questions = normalizeQuiz(await getQuiz());
    if (questions.length !== 10) throw new Error('invalid quiz');
    renderQuestion();
  } catch (error) {
    elements.status.textContent = loadAttempts > 1
      ? `Lần thử ${loadAttempts} chưa thành công. Nút thử lại vẫn ở bên dưới.`
      : 'Chưa tải được câu hỏi. Bác có thể thử lại ngay.';
    showLoadError(error);
  } finally {
    isLoadingQuiz = false;
  }
}

document.addEventListener('keydown', (event) => {
  if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
  const question = questions[currentIndex];
  if (question && !Object.hasOwn(answers, question.id) && ['1', '2'].includes(event.key)) {
    event.preventDefault();
    answerQuestion(event.key === '1');
    return;
  }
  if (event.key === 'Enter' && !elements.card.hidden) {
    const next = elements.card.querySelector('[data-quiz-next]');
    if (next) {
      event.preventDefault();
      next.click();
    }
  }
});

setup();

const displayPrefs = document.getElementById('displayPrefs');
if (displayPrefs) wirePreferences({ root: displayPrefs });
