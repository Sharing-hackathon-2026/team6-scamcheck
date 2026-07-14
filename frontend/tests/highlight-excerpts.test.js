import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildHighlightedSegments,
  findExcerptRanges,
  normalizeWithMap,
} from '../assets/js/highlight-excerpts.js';

test('normalizeWithMap folds Vietnamese case and whitespace while retaining source positions', () => {
  const value = normalizeWithMap('MÃ   OTP\nNgay');
  assert.equal(value.normalized, 'mã otp ngay');
  assert.equal(value.map[0], 0);
  assert.equal(value.map.at(-1), 12);
});

test('findExcerptRanges matches case-insensitively at exact source locations', () => {
  assert.deepEqual(findExcerptRanges('Vui lòng GỬI mã OTP ngay.', ['gửi MÃ otp']), [
    { start: 9, end: 19 },
  ]);
});

test('findExcerptRanges tolerates different whitespace and finds every occurrence', () => {
  assert.deepEqual(findExcerptRanges('OTP   ngay, rồi OTP ngay.', ['otp ngay']), [
    { start: 0, end: 10 },
    { start: 16, end: 24 },
  ]);
});

test('overlapping and duplicate excerpts merge into stable non-nested ranges', () => {
  assert.deepEqual(findExcerptRanges('chuyển tiền ngay hôm nay', [
    'chuyển tiền ngay',
    'tiền ngay hôm nay',
    'CHUYỂN TIỀN NGAY',
  ]), [{ start: 0, end: 24 }]);
});

test('not-found and empty excerpts are ignored', () => {
  assert.deepEqual(findExcerptRanges('Tin bình thường', ['', 'mã OTP', null]), []);
});

test('buildHighlightedSegments preserves hostile text as plain data, never HTML', () => {
  const source = '<img src=x onerror=alert(1)> xin OTP';
  assert.deepEqual(buildHighlightedSegments(source, ['OTP']), [
    { text: '<img src=x onerror=alert(1)> xin ', highlighted: false },
    { text: 'OTP', highlighted: true },
  ]);
});
