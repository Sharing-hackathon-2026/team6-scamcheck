import { ApiError, getQuiz } from './api.js';
import { normalizeQuiz, quizGuidance, scoreQuiz } from './stage4-model.js';

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

function showSummary() {
  const score = scoreQuiz(answers, questions);
  elements.card.hidden = true;
  elements.summary.replaceChildren(
    createElement('p', { className: 'section-eyebrow', text: 'Hoàn thành 10 câu' }),
    createElement('h2', { text: `Bác trả lời đúng ${score}/${questions.length} câu` }),
    createElement('p', { className: 'summary-score', text: quizGuidance(score, questions.length) }),
  );
  const restart = createElement('button', {
    className: 'button-primary', text: 'Luyện lại từ đầu', attributes: { type: 'button' },
  });
  restart.addEventListener('click', () => {
    currentIndex = 0;
    answers = {};
    elements.summary.hidden = true;
    renderQuestion();
  });
  const home = createElement('a', {
    className: 'button-link', text: 'Kiểm tra một tin thật', attributes: { href: '/' },
  });
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
  feedback.append(
    createElement('h3', { text: correct ? 'Bác chọn đúng' : 'Chưa đúng — mình xem lại dấu hiệu nhé' }),
    createElement('p', { text: question.explanation }),
    createElement('p', { className: 'quiz-tip', text: `Mẹo: ${question.tip}` }),
  );
  const next = createElement('button', {
    className: 'button-primary',
    text: currentIndex === questions.length - 1 ? 'Xem tổng kết' : 'Câu tiếp theo',
    attributes: { type: 'button', 'data-quiz-next': 'true' },
  });
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
    [true, 'Có dấu hiệu lừa đảo'],
    [false, 'Có vẻ an toàn'],
  ].forEach(([value, label]) => {
    const button = createElement('button', {
      className: value ? 'button-danger-choice' : 'button-safe-choice',
      text: label,
      attributes: { type: 'button', 'data-answer': String(value), 'aria-pressed': 'false' },
    });
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
  const retry = createElement('button', {
    className: 'button-primary practice-retry',
    text: 'Thử tải lại 10 câu',
    attributes: { type: 'button' },
  });
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
