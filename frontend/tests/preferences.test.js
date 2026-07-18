import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_PREFERENCES,
  FONT_SCALE_OPTIONS,
  fontScaleLabel,
  loadPreferences,
  normalizePreferences,
  PREF_KEY,
  savePreferences,
} from '../assets/js/preferences.js';

function memoryStorage(initial = {}) {
  const store = { ...initial };
  return {
    getItem: (key) => (Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null),
    setItem: (key, value) => { store[key] = String(value); },
    _raw: store,
  };
}

test('DEFAULT_PREFERENCES is high contrast off and font scale 100%', () => {
  assert.deepEqual(DEFAULT_PREFERENCES, { highContrast: false, fontScale: '1' });
  assert.ok(Object.isFrozen(DEFAULT_PREFERENCES));
});

test('FONT_SCALE_OPTIONS exposes exactly three supported levels', () => {
  assert.deepEqual([...FONT_SCALE_OPTIONS], ['1', '1.15', '1.3']);
});

test('normalizePreferences rejects unknown font scales and coerces contrast', () => {
  assert.deepEqual(normalizePreferences({ highContrast: 'yes', fontScale: '2' }), {
    highContrast: false,
    fontScale: '1',
  });
  assert.deepEqual(normalizePreferences({ highContrast: 1, fontScale: '1.3' }), {
    highContrast: false,
    fontScale: '1.3',
  });
  assert.deepEqual(normalizePreferences(null), { ...DEFAULT_PREFERENCES });
  assert.deepEqual(normalizePreferences('rác'), { ...DEFAULT_PREFERENCES });
});

test('fontScaleLabel maps known scales and falls back to 100%', () => {
  assert.equal(fontScaleLabel('1'), '100%');
  assert.equal(fontScaleLabel('1.15'), '115%');
  assert.equal(fontScaleLabel('1.3'), '130%');
  assert.equal(fontScaleLabel('weird'), '100%');
});

test('loadPreferences returns defaults when storage is unavailable or corrupt', () => {
  assert.deepEqual(loadPreferences(undefined), { ...DEFAULT_PREFERENCES });
  assert.deepEqual(loadPreferences({}), { ...DEFAULT_PREFERENCES });
  const corrupt = memoryStorage({ [PREF_KEY]: '{not json' });
  assert.deepEqual(loadPreferences(corrupt), { ...DEFAULT_PREFERENCES });
});

test('loadPreferences reads back saved preferences and ignores junk fields', () => {
  const storage = memoryStorage({
    [PREF_KEY]: JSON.stringify({ highContrast: true, fontScale: '1.3', darkMode: true, token: 'abc' }),
  });
  assert.deepEqual(loadPreferences(storage), { highContrast: true, fontScale: '1.3' });
});

test('savePreferences persists normalized data and returns true', () => {
  const storage = memoryStorage();
  assert.equal(savePreferences(storage, { highContrast: true, fontScale: '1.15', extra: 'x' }), true);
  const stored = JSON.parse(storage.getItem(PREF_KEY));
  assert.deepEqual(stored, { highContrast: true, fontScale: '1.15' });
});

test('savePreferences returns false (not throw) when storage is missing or blocked', () => {
  assert.equal(savePreferences(undefined, { highContrast: true }), false);
  const throwing = {
    getItem: () => null,
    setItem: () => { throw new Error('quota'); },
  };
  assert.equal(savePreferences(throwing, { highContrast: true, fontScale: '1' }), false);
});
