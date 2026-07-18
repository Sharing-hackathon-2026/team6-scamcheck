import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeNfc } from '../assets/js/unicode.js';
import {
  FALLBACK_ACTIONS,
  OUTSIDE_SCOPE_REASON,
  normalizeActions,
  normalizeDetective,
  RISK_META,
} from '../assets/js/result-model.js';

test('normalizeNfc composes Vietnamese combining marks', () => {
  const decomposed = `Ca${'\u0302\u0301'}p nha${'\u0323\u0302'}t`;
  assert.equal(normalizeNfc(decomposed), 'Cấp nhật');
  assert.notEqual(normalizeNfc(decomposed), decomposed);
});

test('the three backend verdicts have friendly UI metadata', () => {
  assert.deepEqual(Object.keys(RISK_META), ['an_toan', 'nghi_ngo', 'nguy_hiem']);
});

test('normalizeActions always returns exactly three unique actions for relevant messages', () => {
  const actions = normalizeActions([' Không gửi OTP. ', 'Không gửi OTP.', '', 'Gọi ngân hàng.']);
  assert.equal(actions.length, 3);
  assert.deepEqual(actions.slice(0, 2), ['Không gửi OTP.', 'Gọi ngân hàng.']);
});

test('normalizeActions uses three safe fallbacks when API actions are absent', () => {
  assert.deepEqual(normalizeActions([]), [...FALLBACK_ACTIONS]);
});

test('normalizeDetective falls back safely for malformed risk and fields', () => {
  const value = normalizeDetective({ risk_level: 'mystery', reason: 1, red_flags: [null], actions: null });
  assert.equal(value.risk_level, 'nghi_ngo');
  assert.match(value.reason, /Chưa đủ thông tin/);
  assert.equal(value.red_flags.length, 0);
  assert.equal(value.actions.length, 3);
});

test('normalizeDetective retains clean excerpts and folds the legacy not-related label into safe', () => {
  const relevant = normalizeDetective({
    risk_level: 'an_toan',
    reason: ' Hợp lệ. ',
    red_flags: [{ label: ' Thông tin ', explanation: ' Bình thường. ', excerpt: ' giao hàng ' }],
    actions: ['a', 'b', 'c'],
  });
  assert.deepEqual(relevant.red_flags[0], {
    label: 'Thông tin', explanation: 'Bình thường.', excerpt: 'giao hàng',
  });
  const legacy = normalizeDetective({
    risk_level: 'khong_lien_quan', red_flags: relevant.red_flags, actions: ['x'],
  });
  assert.equal(legacy.risk_level, 'an_toan');
  assert.equal(legacy.reason, OUTSIDE_SCOPE_REASON);
  assert.deepEqual(legacy.red_flags, []);
  assert.deepEqual(legacy.actions, []);
});
