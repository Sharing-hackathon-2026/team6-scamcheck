// Mô hình hoá phản hồi /api/rescue (Stage 5). Pure helpers — không DOM.
// Mục tiêu: bảo vệ giao diện khi backend trả thiếu/thừa trường, và đảm bảo
// payload gửi đi KHÔNG mang theo lịch sử hay toàn văn dư thừa.

import { normalizeNfc } from './unicode.js?v=stage5-tabs-v15';

export const SITUATIONS = Object.freeze({
  chua_lam_gi: 'Chưa làm gì',
  da_bam_link: 'Đã bấm vào đường link',
  da_chuyen_tien: 'Đã chuyển tiền',
  da_cung_cap_otp: 'Đã cung cấp OTP, PIN hoặc mật khẩu',
});

export const RESCUE_STATUSES = Object.freeze(['complete', 'guarded_fallback', 'not_needed']);

const REASON_LIMIT = 360;
const ACTION_LIMIT = 220;
const DETAIL_LIMIT = 520;
const RED_FLAG_LIMIT = 80;

function cleanText(value, limit = Infinity) {
  if (typeof value !== 'string') return '';
  const collapsed = normalizeNfc(value).replace(/\s+/g, ' ').trim();
  return limit === Infinity ? collapsed : collapsed.slice(0, limit);
}

/** Chỉ giữ lại ký tự an toàn cho giao thức tel: (số, dấu cộng, gạch, khoảng trắng). */
export function sanitizeTel(phone) {
  const cleaned = cleanText(phone);
  if (!cleaned) return '';
  return cleaned.replace(/[^\d+\-\s]/g, '').trim();
}

export function contactHref(phone, channel = 'phone') {
  const sanitized = sanitizeTel(phone);
  if (!sanitized) return '';
  const scheme = channel === 'sms' ? 'sms' : 'tel';
  return `${scheme}:${sanitized.replace(/\s+/g, '')}`;
}

export function telHref(phone) {
  return contactHref(phone, 'phone');
}

function normalizeHotline(value, reviewedAtFallback) {
  const raw = value && typeof value === 'object' ? value : {};
  const phone = cleanText(raw.phone);
  const channel = raw.channel === 'sms' ? 'sms' : 'phone';
  return {
    id: cleanText(raw.id, 60),
    name: cleanText(raw.name, 120) || 'Tổng đài hỗ trợ',
    phone,
    channel,
    contactHref: contactHref(phone, channel),
    type: cleanText(raw.type, 40),
    sourceUrl: cleanText(raw.source_url, 300),
    sourceLabel: cleanText(raw.source_label, 140),
    reviewedAt: cleanText(raw.reviewed_at || reviewedAtFallback, 24),
    emergencyOnly: raw.emergency_only === true,
  };
}

function normalizeStep(value, indexFallback, reviewedAtFallback) {
  const raw = value && typeof value === 'object' ? value : {};
  const step = Number.isFinite(raw.step) ? raw.step : indexFallback;
  const hotlines = (Array.isArray(raw.hotlines) ? raw.hotlines : [])
    .map((item) => normalizeHotline(item, reviewedAtFallback))
    .filter((item) => item.phone)
    .slice(0, 4);
  return {
    step: step,
    key: cleanText(raw.key, 60),
    action: cleanText(raw.action, ACTION_LIMIT),
    detail: cleanText(raw.detail, DETAIL_LIMIT),
    hotlines,
  };
}

/**
 * Chuẩn hoá toàn bộ payload /api/rescue. Không ném; luôn trả object dùng được.
 * Các bước được sắp xếp theo trường `step`; nếu thiếu thì giữ thứ tự nhận được.
 */
export function normalizeRescue(value) {
  const raw = value && typeof value === 'object' ? value : {};
  const reviewedAt = cleanText(raw.reviewed_at, 24);
  const rescue = raw.rescue && typeof raw.rescue === 'object' ? raw.rescue : {};
  const rawSteps = Array.isArray(rescue.steps) ? rescue.steps : [];
  const steps = rawSteps
    .map((item, index) => normalizeStep(item, index + 1, reviewedAt))
    .filter((step) => step.action || step.detail)
    .sort((a, b) => a.step - b.step);
  return {
    situation: Object.hasOwn(SITUATIONS, raw.situation) ? raw.situation : '',
    situationLabel: cleanText(raw.situation_label, 80) || SITUATIONS[raw.situation] || '',
    praise: cleanText(raw.praise, 320) || null,
    rescue: {
      situation: cleanText(rescue.situation, 40) || (Object.hasOwn(SITUATIONS, raw.situation) ? raw.situation : ''),
      headline: cleanText(rescue.headline, REASON_LIMIT),
      reassurance: cleanText(rescue.reassurance, REASON_LIMIT),
      steps,
      closing: cleanText(rescue.closing, REASON_LIMIT),
      isFallback: rescue.is_fallback === true,
    },
    rescueStatus: RESCUE_STATUSES.includes(raw.rescue_status) ? raw.rescue_status : 'guarded_fallback',
    rescueError: cleanText(raw.rescue_error, 320) || null,
    matchedInstitutions: (Array.isArray(raw.matched_institutions) ? raw.matched_institutions : [])
      .map((item) => cleanText(item, 120))
      .filter(Boolean)
      .slice(0, 6),
    safetyNotice: cleanText(raw.safety_notice, 360),
  };
}

/**
 * Dựng payload gửi đi. CHỈ gồm situation + tin nhắn hiện tại + mức rủi ro + dấu hiệu.
 * Không bao giờ kèm lịch sử, excerpt hay dữ liệu cá nhân. Trả null nếu situation sai.
 */
export function buildRescuePayload(situation, { messageText = '', riskLevel = '', redFlags = [] } = {}) {
  if (!Object.hasOwn(SITUATIONS, situation)) return null;
  const flags = (Array.isArray(redFlags) ? redFlags : [])
    .map((flag) => {
      const label = typeof flag === 'string' ? flag : (flag && typeof flag === 'object' ? flag.label : '');
      return cleanText(label, RED_FLAG_LIMIT);
    })
    .filter(Boolean)
    .slice(0, 3);
  return {
    situation,
    message_text: cleanText(messageText),
    risk_level: typeof riskLevel === 'string' ? riskLevel : '',
    red_flags: flags.map((label) => ({ label })),
  };
}
