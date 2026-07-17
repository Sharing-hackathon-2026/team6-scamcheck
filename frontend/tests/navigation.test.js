import test from 'node:test';
import assert from 'node:assert/strict';

import {
  prefetchPage,
  revealCurrentTab,
  setMobileMenuOpen,
  wireTabPrefetch,
} from '../assets/js/navigation.js';

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

test('prefetchPage warms only same-origin page documents once', () => {
  const appended = [];
  const doc = {
    head: { append: (node) => appended.push(node) },
    createElement: () => ({}),
  };
  assert.equal(prefetchPage('/library.html', doc, 'https://scamcheck.example/'), true);
  assert.deepEqual(appended[0], {
    rel: 'prefetch',
    as: 'document',
    href: 'https://scamcheck.example/library.html',
  });
  assert.equal(prefetchPage('/library.html', doc, 'https://scamcheck.example/'), true);
  assert.equal(appended.length, 1);
  assert.equal(prefetchPage('https://evil.example/', doc, 'https://scamcheck.example/'), false);
});

test('wireTabPrefetch warms a tab on pointer, keyboard or touch intent', () => {
  const listeners = new Map();
  const rail = {
    addEventListener: (type, callback) => listeners.set(type, callback),
    setAttribute() {},
  };
  assert.equal(wireTabPrefetch(rail, { head: {}, createElement() {} }), true);
  assert.deepEqual([...listeners.keys()], ['pointerenter', 'focusin', 'touchstart']);
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
