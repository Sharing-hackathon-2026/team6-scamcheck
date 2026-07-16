import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildRescuePayload,
  contactHref,
  normalizeRescue,
  sanitizeTel,
  SITUATIONS,
  telHref,
} from '../assets/js/rescue-model.js';

test('SITUATIONS exposes exactly the four one-tap choices', () => {
  assert.deepEqual([...Object.keys(SITUATIONS)], [
    'chua_lam_gi', 'da_bam_link', 'da_chuyen_tien', 'da_cung_cap_otp',
  ]);
});

test('sanitizeTel strips unsafe characters while keeping dialable digits', () => {
  assert.equal(sanitizeTel('1900 123 456'), '1900 123 456');
  assert.equal(sanitizeTel('Call 113 now!'), '113');
  assert.equal(sanitizeTel('+84 (28) 39.xx'), '+84 28 39');
  assert.equal(sanitizeTel('   '), '');
});

test('telHref collapses spaces and yields a tel: link', () => {
  assert.equal(telHref('1900 123 456'), 'tel:1900123456');
  assert.equal(telHref(''), '');
  assert.equal(contactHref('5656', 'sms'), 'sms:5656');
});

test('buildRescuePayload only carries situation + current message + risk + flag labels', () => {
  const payload = buildRescuePayload('da_chuyen_tien', {
    messageText: '  Chuyển 5 triệu cho STK 1234  ',
    riskLevel: 'nguy_hiem',
    redFlags: [
      { label: ' Yêu cầu chuyển tiền ', explanation: 'đáng ngờ', excerpt: '5 triệu' },
      { label: '', excerpt: 'x' },
      'Chỉ số ngắn',
    ],
  });
  assert.deepEqual(payload, {
    situation: 'da_chuyen_tien',
    message_text: 'Chuyển 5 triệu cho STK 1234',
    risk_level: 'nguy_hiem',
    red_flags: [{ label: 'Yêu cầu chuyển tiền' }, { label: 'Chỉ số ngắn' }],
  });
  // KHÔNG mang theo explanation/excerpt/history.
  assert.ok(!Object.prototype.hasOwnProperty.call(payload, 'history'));
  assert.ok(!payload.red_flags.some((flag) => Object.prototype.hasOwnProperty.call(flag, 'excerpt')));
});

test('buildRescuePayload rejects unknown situations and caps three flags', () => {
  assert.equal(buildRescuePayload('lam_mot_cai_chua_biet', {}), null);
  const payload = buildRescuePayload('chua_lam_gi', {
    redFlags: [{ label: 'A' }, { label: 'B' }, { label: 'C' }, { label: 'D' }],
  });
  assert.equal(payload.red_flags.length, 3);
});

test('normalizeRescue sorts steps by number and keeps hotlines with source metadata', () => {
  const normalized = normalizeRescue({
    situation: 'da_bam_link',
    situation_label: 'Đã bấm vào đường link',
    rescue: {
      headline: ' Hành động ngay ',
      reassurance: ' Bình tĩnh ',
      steps: [
        { step: 3, key: 'report', action: 'Báo cáo', detail: 'Phản ánh', hotlines: [{ id: 'ais_156', name: 'AIS', phone: '156', type: 'cybersecurity', source_url: 'https://ais.gov.vn', source_label: 'AIS', emergency_only: false, reviewed_at: '2026-07-14' }] },
        { step: 1, key: 'disconnect', action: 'Ngắt', detail: 'Đóng trang' },
        { step: 2, key: 'secure', action: 'Đổi mk', detail: 'Thiết bị tin cậy' },
      ],
      closing: 'Cẩn thận',
      is_fallback: false,
    },
    rescue_status: 'complete',
    matched_institutions: [' Vietcombank ', '', 'Techcombank '],
    safety_notice: ' Chỉ số đã đối chiếu. ',
  });
  assert.equal(normalized.situation, 'da_bam_link');
  assert.equal(normalized.rescue.headline, 'Hành động ngay');
  assert.deepEqual(normalized.rescue.steps.map((step) => step.key), ['disconnect', 'secure', 'report']);
  assert.equal(normalized.rescue.steps[2].hotlines[0].contactHref, 'tel:156');
  assert.equal(normalized.rescue.steps[2].hotlines[0].reviewedAt, '2026-07-14');
  assert.deepEqual(normalized.matchedInstitutions, ['Vietcombank', 'Techcombank']);
  assert.equal(normalized.safetyNotice, 'Chỉ số đã đối chiếu.');
});

test('normalizeRescue never throws on hostile/empty payloads and falls back status', () => {
  const empty = normalizeRescue(null);
  assert.equal(empty.situation, '');
  assert.equal(empty.rescueStatus, 'guarded_fallback');
  assert.equal(empty.rescue.steps.length, 0);
  assert.equal(empty.praise, null);

  const garbage = normalizeRescue({ rescue: { steps: [{ step: 'x', hotlines: [{ phone: '   ' }] }], closing: 7 } });
  assert.equal(garbage.rescue.steps.length, 0);
  assert.equal(garbage.rescue.closing, '');
});

test('normalizeRescue surfaces chua_lam_gi praise without inventing AI calls', () => {
  const normalized = normalizeRescue({
    situation: 'chua_lam_gi',
    praise: ' Bác đã dừng đúng lúc. ',
    rescue: { steps: [], closing: 'Cẩn thận' },
    rescue_status: 'not_needed',
  });
  assert.equal(normalized.praise, 'Bác đã dừng đúng lúc.');
  assert.equal(normalized.rescueStatus, 'not_needed');
});
