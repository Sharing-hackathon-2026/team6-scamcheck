import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildShareCardModel,
  redactPrivateSequences,
  safeFileName,
  SHARE_CARD_DEFAULTS,
  wrapLines,
} from '../assets/js/share-card.js';

test('buildShareCardModel keeps risk label, capped reason and at most three sign labels', () => {
  const model = buildShareCardModel({
    risk_level: 'nguy_hiem',
    reason: '  Yêu cầu   OTP và   link giả ngân hàng. ',
    red_flags: [
      { label: ' Yêu cầu OTP ', explanation: 'đáng ngờ', excerpt: 'gửi mã OTP' },
      { label: 'Link lạ', excerpt: 'https://x.example' },
      { label: 'Giục giã', excerpt: '30 phút' },
      { label: 'Số tài khoản', excerpt: '1234' },
    ],
  });
  assert.equal(model.riskKey, 'nguy_hiem');
  assert.equal(model.riskLabel, 'Nguy hiểm');
  assert.equal(model.reason, 'Yêu cầu OTP và link giả ngân hàng.');
  assert.equal(model.signs.length, 3);
  assert.deepEqual(model.signs, ['Yêu cầu OTP', 'Link lạ', 'Giục giã']);
});

test('buildShareCardModel never exposes message text, excerpts or account numbers', () => {
  const model = buildShareCardModel({
    risk_level: 'nghi_ngo',
    reason: 'r',
    red_flags: [{ label: 'A', excerpt: 'STK 9999 8888 7777' }],
  }, { url: 'https://scamcheck.example' });
  const serialized = JSON.stringify(model);
  assert.ok(!serialized.includes('9999'));
  assert.ok(!serialized.includes('7777'));
  assert.ok(!serialized.includes('excerpt'));
  assert.ok(!Object.prototype.hasOwnProperty.call(model, 'text'));
  assert.ok(!serialized.includes('STK'));
  assert.equal(model.url, 'https://scamcheck.example');
});

test('share summary redacts URLs, emails and phone/account-like digit sequences', () => {
  const safe = redactPrivateSequences(
    'Gọi 0909 123 456, chuyển STK 123456789 tại https://evil.example hoặc a@b.example',
  );
  assert.ok(!safe.includes('0909'));
  assert.ok(!safe.includes('123456789'));
  assert.ok(!safe.includes('evil.example'));
  assert.ok(!safe.includes('a@b.example'));
  assert.match(safe, /đã ẩn/);
});

test('buildShareCardModel falls back to risk label when reason is empty', () => {
  const model = buildShareCardModel({ risk_level: 'an_toan', reason: '   ', red_flags: [] });
  assert.equal(model.reason, 'An toàn');
  assert.deepEqual(model.signs, []);
});

test('buildShareCardModel caps over-long signs and reasons', () => {
  const long = 'Dấu hiệu rất dài '.repeat(30);
  const model = buildShareCardModel({ risk_level: 'nguy_hiem', reason: long, red_flags: [{ label: long }] });
  assert.ok(model.reason.length <= 132);
  assert.ok(model.signs[0].length <= 56);
  assert.ok(model.reason.endsWith('…'));
  assert.ok(model.signs[0].endsWith('…'));
});

test('wrapLines breaks text to fit maxWidth using the provided measure', () => {
  // measure trả số ký tự → mô phỏng chiều rộng cố định.
  const charMeasure = (text) => text.length;
  assert.deepEqual(wrapLines(charMeasure, 'ngắn', 10), ['ngắn']);
  assert.deepEqual(wrapLines(charMeasure, 'một hai ba', 7), ['một hai', 'ba']);
  assert.deepEqual(wrapLines(charMeasure, 'chữrất dài không có khoảng trắng', 4), ['chữrất', 'dài', 'không', 'có', 'khoảng', 'trắng']);
});

test('wrapLines handles empty/missing input safely', () => {
  assert.deepEqual(wrapLines(() => 100, '', 10), ['']);
  assert.deepEqual(wrapLines(null, 'x', 10), ['x']);
});

test('safeFileName produces a slug + safe extension', () => {
  assert.equal(safeFileName('ScamCheck cảnh báo'), 'scamcheck-canh-bao.png');
  assert.equal(safeFileName('!!!---   ', 'PNG'), 'scamcheck.png');
  assert.equal(safeFileName('ảnh', '../../etc'), 'anh.png');
  assert.equal(safeFileName('a'.repeat(200), 'jpeg'), `${'a'.repeat(48)}.jpeg`);
});

test('SHARE_CARD_DEFAULTS uses 1080x1350 without carrying personal data', () => {
  assert.equal(SHARE_CARD_DEFAULTS.width, 1080);
  assert.equal(SHARE_CARD_DEFAULTS.height, 1350);
  assert.ok(SHARE_CARD_DEFAULTS.reminder.length > 0);
  assert.ok(SHARE_CARD_DEFAULTS.qualifier.length > 0);
});
