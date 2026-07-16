import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel) => readFileSync(join(here, rel), 'utf8');

// Trang kiểm tra (/) phải độc lập với thư viện: app.js không được fetch
// /api/scam-library và không được assume các node thư viện tồn tại. Thư viện
// đã tách ra library.js và chỉ chạy khi các node đó có mặt.
test('app.js no longer imports or touches the scam library', () => {
  const app = read('../assets/js/app.js');
  for (const forbidden of [
    'getScamLibrary',   // fetch of /api/scam-library only flows through this import
    'setupLibrary',
    'libraryList',
    'libraryFilters',
    'libraryToggleBtn',
    'renderLibrary',
    'setLibraryCollapsed',
  ]) {
    assert.ok(!app.includes(forbidden), `app.js must not reference "${forbidden}"`);
  }
});

test('library.js owns the library API + DOM wiring', () => {
  const lib = read('../assets/js/library.js');
  assert.ok(lib.includes('getScamLibrary'), 'library.js should fetch the library');
  assert.ok(lib.includes('libraryList'), 'library.js should wire the list');
  assert.ok(lib.includes('libraryFilters'), 'library.js should wire the filters');
  assert.ok(lib.includes('librarySearch'), 'library.js should wire text search');
  assert.ok(lib.includes('setupLibrary'), 'library.js should export setupLibrary');
  assert.ok(lib.includes('getElementById("libraryList")'), 'setupLibrary should guard on node existence');
  assert.ok(lib.includes('library-empty'), 'library should expose a real empty state');
  assert.ok(lib.includes('Thử tải lại thư viện'), 'library error should have a retry path');
});

test('all three entry scripts use the shared cache-bust version', () => {
  for (const file of ['index.html', 'library.html', 'practice.html']) {
    const html = read(`../${file}`);
    assert.ok(html.includes('v=stage5-tabs-v8'), `${file} must use stage5-tabs-v8`);
    assert.ok(html.includes('/assets/js/navigation.js?v=stage5-tabs-v8'), `${file} must reveal its active tab`);
  }
  const app = read('../assets/js/app.js');
  const library = read('../assets/js/library.js');
  assert.ok(app.includes("./result-model.js?v=stage5-tabs-v8"));
  assert.ok(app.includes("./share-card.js?v=stage5-tabs-v8"));
  assert.ok(library.includes('./stage3-model.js?v=stage5-tabs-v8'));
});
