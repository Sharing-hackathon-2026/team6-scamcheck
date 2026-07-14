export const RISK_META = Object.freeze({
  an_toan: { label: 'An toàn', announcement: 'Kết quả: An toàn' },
  nghi_ngo: { label: 'Nghi ngờ', announcement: 'Kết quả: Nghi ngờ' },
  nguy_hiem: { label: 'Nguy hiểm', announcement: 'Kết quả: Nguy hiểm' },
  khong_lien_quan: { label: 'Không liên quan', announcement: 'Kết quả: Không liên quan' },
});

export const FALLBACK_ACTIONS = Object.freeze([
  'Không bấm liên kết, không cung cấp mã OTP hoặc mật khẩu.',
  'Liên hệ tổ chức qua số điện thoại chính thức do bác tự tìm.',
  'Chặn người gửi và báo cho người thân nếu bác vẫn còn nghi ngờ.',
]);

function cleanText(value) {
  return typeof value === 'string' ? value.trim() : '';
}

/** Bảo đảm giao diện luôn có đúng ba hành động cho ba mức rủi ro chính. */
export function normalizeActions(actions, riskLevel) {
  if (riskLevel === 'khong_lien_quan') return [];
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
  const riskLevel = Object.hasOwn(RISK_META, detective.risk_level)
    ? detective.risk_level
    : 'nghi_ngo';
  const redFlags = (Array.isArray(detective.red_flags) ? detective.red_flags : [])
    .filter((flag) => flag && typeof flag === 'object')
    .map((flag) => ({
      label: cleanText(flag.label) || 'Dấu hiệu cần chú ý',
      explanation: cleanText(flag.explanation),
      excerpt: cleanText(flag.excerpt),
    }));

  return {
    risk_level: riskLevel,
    reason: cleanText(detective.reason) || 'Chưa đủ thông tin để kết luận chắc chắn. Bác nên kiểm tra lại qua kênh chính thức.',
    red_flags: riskLevel === 'khong_lien_quan' ? [] : redFlags,
    actions: normalizeActions(detective.actions, riskLevel),
  };
}
