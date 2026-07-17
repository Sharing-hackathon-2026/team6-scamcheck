import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  offersRescueGuidance,
  offersShareCard,
  RISK_META,
} from '../assets/js/result-model.js';

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel) => readFileSync(join(here, rel), 'utf8');
const css = read('../assets/css/app.css');
const tokens = read('../assets/css/tokens.css');
const app = read('../assets/js/app.js');
const navigation = read('../assets/js/navigation.js');
const api = read('../assets/js/api.js');
const historyPage = read('../assets/js/history-page.js');
const nginx = read('../../deploy/nginx.conf');

// #5 multi-step flow: rescue guidance only for risky verdicts; the question is
// revealed behind the Continue action. Share card offered for the three verdicts
// that carry a useful summary (not for "khong_lien_quan").
test('offersRescueGuidance is true only for nghi_ngo / nguy_hiem', () => {
  assert.equal(offersRescueGuidance('nguy_hiem'), true);
  assert.equal(offersRescueGuidance('nghi_ngo'), true);
  assert.equal(offersRescueGuidance('an_toan'), false);
  assert.equal(offersRescueGuidance('khong_lien_quan'), false);
  assert.equal(offersRescueGuidance(undefined), false);
  assert.equal(offersRescueGuidance('bogus'), false);
});

test('offersShareCard is true for an_toan / nghi_ngo / nguy_hiem only', () => {
  assert.equal(offersShareCard('an_toan'), true);
  assert.equal(offersShareCard('nghi_ngo'), true);
  assert.equal(offersShareCard('nguy_hiem'), true);
  assert.equal(offersShareCard('khong_lien_quan'), false);
  assert.equal(offersShareCard(undefined), false);
});

test('every RISK_META key has a defined Vietnamese label', () => {
  for (const [key, meta] of Object.entries(RISK_META)) {
    assert.ok(typeof meta.label === 'string' && meta.label.length > 0, `${key} label`);
    assert.ok(typeof meta.announcement === 'string' && meta.announcement.length > 0, `${key} announcement`);
  }
});

// #6 dashed connector centred on the number column via a CSS variable, not a
// magic offset. Must stop before the final item.
test('action-list connector uses a number-column variable centred, not a magic offset', () => {
  const ol = css.match(/\.action-list\s*\{[\s\S]*?\}/);
  assert.ok(ol, '.action-list block exists');
  assert.match(ol[0], /--step-number-col:/);
  const li = css.match(/\.action-list li\s*\{[\s\S]*?\}/);
  assert.ok(li, '.action-list li block exists');
  assert.match(li[0], /grid-template-columns:\s*var\(--step-number-col\)\s+minmax\(0,\s*1fr\)/);
  const after = css.match(/\.action-list li::after\s*\{[\s\S]*?\}/);
  assert.ok(after, '.action-list li::after exists');
  assert.match(after[0], /left:\s*calc\(var\(--step-number-col\)\s*\/\s*2\)/);
  assert.ok(!/left:\s*1\.5rem/.test(after[0]), 'no magic 1.5rem offset on the connector');
  assert.match(css, /\.action-list li:last-child::after\s*\{\s*display:\s*none;?\s*\}/);
});

// #1 hover corner bug: library + technical summaries round to the parent radius
// so the hover wash never paints a square corner beyond the rounded surface.
test('library + technical summaries inherit the parent radius in both states', () => {
  assert.match(css, /\.library-item-summary\s*\{[^}]*border-radius:\s*var\(--item-radius\)\s+var\(--item-radius\)\s+0\s+0/);
  assert.match(css, /\.library-item:not\(\[open\]\)\s*\.library-item-summary\s*\{\s*border-radius:\s*var\(--item-radius\)/);
  assert.match(css, /\.technical-analysis:not\(\[open\]\)\s*\.technical-summary\s*\{\s*border-radius:\s*var\(--tech-radius\)/);
});

// #4 decision box: four equal-track choices that collapse to one column on mobile.
test('rescue decision choices are an equal 2-track grid collapsing to one column on mobile', () => {
  assert.match(css, /\.rescue-choices\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/);
  assert.match(css, /\.rescue-choices\s*\{[\s\S]*?grid-auto-rows:\s*1fr/);
  // mobile collapse present somewhere in a narrow media query
  assert.match(css, /@media[^{]*max-width:\s*560px[\s\S]*?\.rescue-choices\s*\{[^}]*grid-template-columns:\s*1fr/);
  // choices meet the >=44px target minimum
  const choice = css.match(/\.rescue-choice\s*\{[\s\S]*?min-height:\s*(\d+)px/);
  assert.ok(choice, 'rescue-choice has a min-height');
  assert.ok(Number(choice[1]) >= 44, `rescue-choice min-height ${choice[1]} >= 44`);
});

// #5 multi-step: rescue section is hidden-able and clears the sticky header.
test('rescue section supports hiding and a sticky-header-safe scroll margin', () => {
  assert.match(css, /\.rescue-section\[hidden\]\s*\{\s*display:\s*none\s*!important/);
  assert.match(css, /\.rescue-section\s*\{[^}]*scroll-margin-top:\s*\d+px/);
  assert.match(css, /@media[^{]*max-width:\s*700px[\s\S]*?\.rescue-section\s*\{[^}]*scroll-margin-top:\s*88px/);
  assert.match(css, /\.continue-gate\s*\{/);
});

test('continuing to rescue collapses the three expandable explanations', () => {
  assert.match(app, /querySelectorAll\('\.rescue-collapsible\[open\]'\)/);
  assert.match(app, /details\.removeAttribute\('open'\)/);
  for (const title of ['Đoạn đáng chú ý trong tin gốc', 'Dấu hiệu cần chú ý', 'Cô tâm lý giải thích']) {
    assert.ok(app.includes(title), `${title} remains available in a disclosure`);
  }
  assert.match(css, /\.result-disclosure-summary\s*\{/);
});

test('mobile navigation uses an accessible hamburger menu on all pages', () => {
  for (const page of ['index.html', 'library.html', 'practice.html', 'history.html']) {
    const html = read(`../${page}`);
    assert.match(html, /class="mobile-menu-toggle"[^>]*aria-expanded="false"[^>]*aria-controls="primaryNav"/);
    assert.match(html, /<nav id="primaryNav" class="tab-rail"/);
  }
  assert.match(navigation, /event\.key !== 'Escape'/);
  assert.match(css, /@media[^{]*max-width:\s*700px[\s\S]*?\.mobile-menu-toggle\s*\{\s*display:\s*inline-flex/);
});

test('share QR request bypasses stale cached internal-port SVG', () => {
  assert.ok(api.includes('/api/share/qr.svg?v=portless-v1'));
  assert.match(api, /cache:\s*'no-store'/);
});

test('check workflow auto-scrolls at the three requested transitions', () => {
  assert.match(app, /hero\.addEventListener\('dblclick',\s*goToInput\)/);
  assert.match(app, /hero\.addEventListener\('pointerup'/);
  assert.match(app, /if \(verdictCard\) scrollToBlock\(verdictCard\)/);
  assert.match(app, /scrollToBlock\(rescueCard, \{ focus: true \}\)/);
  for (const selector of ['.input-card', '.risk-card', '.rescue-card']) {
    const escaped = selector.replace('.', '\\.');
    assert.match(css, new RegExp(`${escaped}\\s*\\{[^}]*scroll-margin-top:\\s*96px`));
  }
  assert.match(css, /\.hero\s*\{[^}]*touch-action:\s*manipulation/);
});

// #4 decision tokens exist across light/dark/high-contrast.
test('AI history page exposes session stats and a dedicated exe.dev admin gate', () => {
  const html = read('../history.html');
  const historyJs = read('../assets/js/history-page.js');
  assert.match(html, /class="risk-pie"/);
  assert.match(html, /class="ai-log-table"/);
  assert.match(html, /id="adminLogin"[^>]*:8001\/__exe\.dev\/login/);
  assert.match(html, /id="adminExports"[^>]*hidden/);
  assert.ok(historyJs.includes("location.hostname}:8001"));
  assert.ok(historyJs.includes("isAdmin ? personalHistoryUrl() : adminLoginUrl()"));
  assert.ok(historyJs.includes("cache: 'no-store'"));
  assert.ok(!historyJs.includes('innerHTML'));
});

test('shared assets use immutable browser cache and tab documents warm on intent', () => {
  assert.match(nginx, /location \/assets\/[\s\S]*?expires\s+1y/);
  assert.match(nginx, /Cache-Control\s+"public, immutable"/);
  assert.match(tokens, /url\("\/assets\/fonts\/material-symbols-rounded\.woff2"\)/);
  assert.match(navigation, /link\.rel\s*=\s*'prefetch'/);
  assert.match(navigation, /link\.as\s*=\s*'document'/);
  assert.match(navigation, /wireTabPrefetch\(rail\)/);
  assert.match(historyPage, /personalHistoryUrl/);
});

test('decision-box tokens are defined for light, dark and high-contrast', () => {
  for (const t of ['--color-decision-bg', '--color-decision-text', '--color-decision-choice-text']) {
    assert.ok(tokens.includes(t), `light token ${t}`);
  }
  // dark override + HC overrides each set the edge token
  const darkCount = (tokens.match(/--color-decision-bg:/g) || []).length;
  assert.ok(darkCount >= 2, 'decision bg defined in at least light + dark');
  assert.match(tokens, /html\[data-high-contrast="true"\][\s\S]*?--color-decision-edge:/);
});

// #7 hero illustration is decorative, behind copy, and hidden on narrow screens.
test('hero illustration is decorative and protected from narrow-screen overflow', () => {
  assert.match(css, /\.hero-illustration\s*\{[\s\S]*?pointer-events:\s*none/);
  assert.match(css, /\.hero-illustration\s*\{[\s\S]*?z-index:\s*0/);
  assert.match(css, /@media[^{]*max-width:\s*700px[\s\S]*?\.hero-illustration\s*\{\s*display:\s*none/);
  for (const page of ['index.html', 'library.html', 'practice.html', 'history.html']) {
    const html = read(`../${page}`);
    assert.match(html, /<svg class="hero-illustration"[^>]*aria-hidden="true"/, `${page} has decorative hero illustration`);
    assert.match(html, /<svg class="hero-arc"[^>]*aria-hidden="true"/, `${page} keeps the broad arcs`);
  }
});
