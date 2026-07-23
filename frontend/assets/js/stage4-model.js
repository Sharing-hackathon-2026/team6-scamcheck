import { normalizeNfc } from './unicode.js?v=stage5-tabs-v16';

function clean(value) {
  return typeof value === 'string' ? normalizeNfc(value).trim() : '';
}

export function normalizeTechnicalAnalysis(value) {
  const source = value && typeof value === 'object' ? value : {};
  const links = (Array.isArray(source.links) ? source.links : []).slice(0, 5).map((link) => ({
    source_url: clean(link?.source_url),
    original_domain: clean(link?.original_domain),
    final_domain: clean(link?.final_domain),
    resolved: link?.resolved === true,
    warnings: (Array.isArray(link?.warnings) ? link.warnings : []).slice(0, 4).map((warning) => ({
      code: clean(warning?.code),
      reason: clean(warning?.reason),
    })).filter((warning) => warning.reason),
  })).filter((link) => link.source_url || link.original_domain);
  const ruleSignals = (Array.isArray(source.rule_signals) ? source.rule_signals : []).slice(0, 8)
    .map((signal) => ({
      code: clean(signal?.code),
      severity: ['danger', 'warning'].includes(signal?.severity) ? signal.severity : 'warning',
      label: clean(signal?.label) || 'Tín hiệu cần kiểm tra',
      excerpt: clean(signal?.excerpt),
      explanation: clean(signal?.explanation),
    }));
  return { links, ruleSignals };
}

export function normalizeQuiz(value) {
  const questions = Array.isArray(value?.questions) ? value.questions : [];
  return questions.map((item) => ({
    id: clean(item?.id),
    text: clean(item?.text),
    is_scam: item?.is_scam === true,
    category: clean(item?.category),
    explanation: clean(item?.explanation),
    tip: clean(item?.tip),
  })).filter((item) => item.id && item.text && item.explanation && item.tip);
}

export function scoreQuiz(answers, questions) {
  const answerMap = answers && typeof answers === 'object' ? answers : {};
  return questions.reduce(
    (score, question) => score + (answerMap[question.id] === question.is_scam ? 1 : 0),
    0,
  );
}

export function quizGuidance(score, total) {
  if (score === total) return 'Bác nhận diện rất tốt. Hãy tiếp tục giữ thói quen dừng lại và xác minh.';
  if (score >= Math.ceil(total * 0.7)) return 'Bác đã nắm phần lớn dấu hiệu. Hãy chú ý thêm các tin tạo áp lực hoặc xin dữ liệu.';
  return 'Không sao, đây là lúc luyện tập. Hãy nhớ: dừng lại, không gửi mã và tự tìm kênh chính thức.';
}
