import { normalizeNfc } from './unicode.js';

export const RISK_META = Object.freeze({
  an_toan: { label: 'An toàn', announcement: 'Kết quả: An toàn' },
  nghi_ngo: { label: 'Nghi ngờ', announcement: 'Kết quả: Nghi ngờ' },
  nguy_hiem: { label: 'Nguy hiểm', announcement: 'Kết quả: Nguy hiểm' },
});

// Stage 5 multi-step flow gating (single source of truth, unit-tested):
// rescue guidance is only offered when the verdict is risky, and the share
// card is offered for the three verdicts that carry a useful summary. The
// rescue question itself is revealed behind the Continue action in app.js.
const RESCUE_RISK_LEVELS = new Set(['nghi_ngo', 'nguy_hiem']);
const SHARE_RISK_LEVELS = new Set(['an_toan', 'nghi_ngo', 'nguy_hiem']);

export function offersRescueGuidance(riskLevel) {
  return RESCUE_RISK_LEVELS.has(riskLevel);
}

export function offersShareCard(riskLevel) {
  return SHARE_RISK_LEVELS.has(riskLevel);
}

export const OUTSIDE_SCOPE_REASON = 'Tin nhắn không thuộc nội dung cần kiểm tra lừa đảo.';

export const FALLBACK_ACTIONS = Object.freeze([
  'Không bấm liên kết, không cung cấp mã OTP hoặc mật khẩu.',
  'Liên hệ tổ chức qua số điện thoại chính thức do bác tự tìm.',
  'Chặn người gửi và báo cho người thân nếu bác vẫn còn nghi ngờ.',
]);

function cleanText(value) {
  return typeof value === 'string' ? normalizeNfc(value).trim() : '';
}

/** Bảo đảm giao diện luôn có đúng ba hành động cho ba mức rủi ro chính. */
export function normalizeActions(actions) {
  const unique = [];
  (Array.isArray(actions) ? actions : []).forEach((action) => {
    const cleaned = cleanText(action);
    if (cleaned && !unique.includes(cleaned) && unique.length < 3) unique.push(cleaned);
  });
  for (const fallback of FALLBACK_ACTIONS) {
    if (unique.length === 3) break;
    if (!unique.includes(fallback)) unique.push(fallback);
  }
  return unique.slice(0, 3);
}

export function normalizeDetective(value) {
  const detective = value && typeof value === 'object' ? value : {};
  const legacyOutsideScope = detective.risk_level === 'khong_lien_quan';
  const riskLevel = legacyOutsideScope
    ? 'an_toan'
    : Object.hasOwn(RISK_META, detective.risk_level) ? detective.risk_level : 'nghi_ngo';
  const redFlags = (Array.isArray(detective.red_flags) ? detective.red_flags : [])
    .filter((flag) => flag && typeof flag === 'object')
    .map((flag) => ({
      label: cleanText(flag.label) || 'Dấu hiệu cần chú ý',
      explanation: cleanText(flag.explanation),
      excerpt: cleanText(flag.excerpt),
    }));

  const cleanedReason = cleanText(detective.reason);
  const outsideScope = legacyOutsideScope || cleanedReason === OUTSIDE_SCOPE_REASON;
  return {
    risk_level: riskLevel,
    reason: outsideScope
      ? OUTSIDE_SCOPE_REASON
      : cleanedReason || 'Chưa đủ thông tin để kết luận chắc chắn. Bác nên kiểm tra lại qua kênh chính thức.',
    red_flags: outsideScope ? [] : redFlags,
    actions: outsideScope ? [] : normalizeActions(detective.actions),
  };
}
