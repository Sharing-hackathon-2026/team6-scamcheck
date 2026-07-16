import test from 'node:test';
import assert from 'node:assert/strict';
import { MATERIAL_ICONS, iconChar } from '../assets/js/icons.js';

test('MATERIAL_ICONS is frozen and maps each name to one Private-Use codepoint', () => {
  assert.equal(Object.isFrozen(MATERIAL_ICONS), true);
  for (const [name, char] of Object.entries(MATERIAL_ICONS)) {
    assert.equal(typeof char, 'string', `${name} should be a string`);
    assert.equal([...char].length, 1, `${name} should be exactly one codepoint`);
    const code = char.codePointAt(0);
    // Material Symbols live in the Supplementary Private Use Area-A (U+E000..U+F8FF).
    assert.ok(code >= 0xe000 && code <= 0xf8ff, `${name} (${code.toString(16)}) should be in PUA`);
  }
});

test('iconChar returns empty string for unknown names', () => {
  assert.equal(iconChar('definitely_not_an_icon'), '');
  assert.equal(iconChar(''), '');
});

test('the icon family covers every ScamCheck control the UI depends on', () => {
  const required = [
    'shield', 'fact_check', 'menu_book', 'quiz',   // brand + nav
    'mic', 'delete', 'contrast', 'text_increase',  // input + display prefs
    'history', 'warning', 'call', 'sms',           // history + risk + hotlines
    'share', 'download', 'check_circle', 'refresh',// share card + retry
    'support_agent', 'rule', 'campaign', 'arrow_forward',
  ];
  for (const name of required) {
    assert.ok(name in MATERIAL_ICONS, `missing required icon: ${name}`);
  }
});
