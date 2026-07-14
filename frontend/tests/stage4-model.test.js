import test from 'node:test';
import assert from 'node:assert/strict';

import {
  normalizeQuiz,
  normalizeTechnicalAnalysis,
  quizGuidance,
  scoreQuiz,
} from '../assets/js/stage4-model.js';

test('technical analysis normalizes typed links and rule signals', () => {
  const result = normalizeTechnicalAnalysis({
    links: [{
      source_url: 'bit.ly/a', original_domain: 'bit.ly', final_domain: 'evil.example',
      resolved: true, warnings: [{ code: 'shortener', reason: 'Che đích' }],
    }],
    rule_signals: [{
      code: 'credential_request', severity: 'danger', label: 'OTP',
      excerpt: 'gửi OTP', explanation: 'Không cung cấp.',
    }],
  });
  assert.equal(result.links[0].final_domain, 'evil.example');
  assert.equal(result.ruleSignals[0].severity, 'danger');
});

test('technical analysis handles hostile malformed local data', () => {
  assert.deepEqual(normalizeTechnicalAnalysis(null), { links: [], ruleSignals: [] });
  const value = normalizeTechnicalAnalysis({ links: [{ source_url: '<script>', warnings: 'bad' }] });
  assert.equal(value.links[0].source_url, '<script>');
  assert.deepEqual(value.links[0].warnings, []);
});

test('quiz normalization, scoring and guidance cover full state', () => {
  const questions = normalizeQuiz({ questions: [
    { id: '1', text: 'A', is_scam: true, category: 'C', explanation: 'E', tip: 'T' },
    { id: '2', text: 'B', is_scam: false, category: 'C', explanation: 'E', tip: 'T' },
  ] });
  assert.equal(scoreQuiz({ 1: true, 2: true }, questions), 1);
  assert.match(quizGuidance(2, 2), /rất tốt/);
  assert.match(quizGuidance(0, 2), /Không sao/);
});
