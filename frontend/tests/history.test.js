import test from 'node:test';
import assert from 'node:assert/strict';
import {
  HISTORY_KEY,
  HISTORY_LIMIT,
  addHistoryEntry,
  clearHistory,
  deleteHistoryEntry,
  loadHistory,
  saveHistory,
} from '../assets/js/history.js';

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, value); },
    value(key) { return values.get(key); },
  };
}

const detective = { risk_level: 'nghi_ngo', reason: 'Cần kiểm tra.', red_flags: [], actions: ['1', '2', '3'] };

test('addHistoryEntry puts newest first and caps history at ten', () => {
  let entries = [];
  for (let index = 0; index < 12; index += 1) {
    entries = addHistoryEntry(entries, { id: `id-${index}`, text: `Tin ${index}`, detective, now: index });
  }
  assert.equal(entries.length, HISTORY_LIMIT);
  assert.equal(entries[0].text, 'Tin 11');
  assert.equal(entries.at(-1).text, 'Tin 2');
});

test('adding the same text replaces the older entry instead of duplicating it', () => {
  const oldEntry = addHistoryEntry([], { id: 'old', text: 'Tin giống nhau', detective, now: 1 });
  const updated = addHistoryEntry(oldEntry, { id: 'new', text: 'Tin giống nhau', detective, now: 2 });
  assert.equal(updated.length, 1);
  assert.equal(updated[0].id, 'new');
});

test('saveHistory and loadHistory round-trip valid local data', () => {
  const storage = memoryStorage();
  const entries = addHistoryEntry([], { id: 'one', text: 'Tin cần xem', detective, now: 10 });
  assert.equal(saveHistory(storage, entries), true);
  assert.deepEqual(loadHistory(storage), entries);
  assert.match(storage.value(HISTORY_KEY), /Tin cần xem/);
});

test('loadHistory gracefully ignores corrupt JSON and unavailable storage', () => {
  assert.deepEqual(loadHistory(memoryStorage({ [HISTORY_KEY]: '{bad' })), []);
  assert.deepEqual(loadHistory(null), []);
  const throwing = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  assert.deepEqual(loadHistory(throwing), []);
  assert.equal(saveHistory(throwing, []), false);
});

test('delete one and clear all history are immutable operations', () => {
  const entries = [
    { id: 'a', text: 'A', detective, createdAt: 1 },
    { id: 'b', text: 'B', detective, createdAt: 2 },
  ];
  assert.deepEqual(deleteHistoryEntry(entries, 'a').map((item) => item.id), ['b']);
  assert.deepEqual(clearHistory(entries), []);
  assert.equal(entries.length, 2);
});
