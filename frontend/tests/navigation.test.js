import test from 'node:test';
import assert from 'node:assert/strict';

import { revealCurrentTab, setMobileMenuOpen } from '../assets/js/navigation.js';

test('revealCurrentTab centers the active tab inside an overflowing rail', () => {
  const calls = [];
  const current = { offsetLeft: 420, offsetWidth: 120 };
  const rail = {
    scrollWidth: 620,
    clientWidth: 360,
    querySelector: () => current,
    scrollTo: (options) => calls.push(options),
  };
  assert.equal(revealCurrentTab(rail), true);
  assert.deepEqual(calls, [{ left: 260, behavior: 'auto' }]);
});

test('revealCurrentTab is a no-op without a rail or current page', () => {
  assert.equal(revealCurrentTab(null), false);
  assert.equal(revealCurrentTab({ querySelector: () => null, scrollTo() {} }), false);
});

test('setMobileMenuOpen synchronizes expanded state and menu visibility', () => {
  const toggleAttributes = new Map();
  const railAttributes = new Map();
  const toggle = { setAttribute: (key, value) => toggleAttributes.set(key, value) };
  const rail = {
    setAttribute: (key, value) => railAttributes.set(key, value),
    removeAttribute: (key) => railAttributes.delete(key),
  };
  assert.equal(setMobileMenuOpen(toggle, rail, true), true);
  assert.equal(toggleAttributes.get('aria-expanded'), 'true');
  assert.equal(toggleAttributes.get('aria-label'), 'Đóng trình đơn chính');
  assert.equal(railAttributes.get('data-open'), 'true');
  assert.equal(setMobileMenuOpen(toggle, rail, false), false);
  assert.equal(toggleAttributes.get('aria-expanded'), 'false');
  assert.equal(toggleAttributes.get('aria-label'), 'Mở trình đơn chính');
  assert.equal(railAttributes.has('data-open'), false);
});
