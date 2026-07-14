import test from 'node:test';
import assert from 'node:assert/strict';
import {
  filterLibraryItems,
  libraryGroupFromHash,
  normalizePsychologist,
} from '../assets/js/stage3-model.js';

const items = [{ id: 'a', group: 'fake_bank' }, { id: 'b', group: 'delivery' }];

test('normalizePsychologist keeps complete message and independent errors', () => {
  assert.deepEqual(normalizePsychologist({ message: ' Cô hiểu bác đang lo. Bác cứ dừng lại. ' }, 'complete'), {
    status: 'complete', message: 'Cô hiểu bác đang lo. Bác cứ dừng lại.', error: '',
  });
  assert.equal(normalizePsychologist(null, 'unavailable', 'Tạm bận').error, 'Tạm bận');
});

test('library helpers filter without reload state and validate hash', () => {
  assert.deepEqual(filterLibraryItems(items, 'fake_bank'), [items[0]]);
  assert.deepEqual(filterLibraryItems(items, 'all'), items);
  assert.equal(libraryGroupFromHash('#delivery', ['fake_bank', 'delivery']), 'delivery');
  assert.equal(libraryGroupFromHash('#unknown', ['fake_bank']), 'all');
});
