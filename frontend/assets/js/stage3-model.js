import { normalizeNfc } from './unicode.js';

export function normalizePsychologist(value, status = 'not_needed', error = '') {
  const message = value && typeof value.message === 'string'
    ? normalizeNfc(value.message).trim()
    : '';
  const safeStatus = ['complete', 'not_needed', 'unavailable'].includes(status)
    ? status
    : 'unavailable';
  return {
    status: message && safeStatus === 'complete' ? 'complete' : safeStatus,
    message,
    error: typeof error === 'string' ? normalizeNfc(error).trim() : '',
  };
}

export function filterLibraryItems(items, group = 'all') {
  const source = Array.isArray(items) ? items : [];
  return group === 'all' ? source : source.filter((item) => item?.group === group);
}

export function libraryGroupFromHash(hash, validGroups) {
  const key = String(hash || '').replace(/^#/, '');
  return Array.isArray(validGroups) && validGroups.includes(key) ? key : 'all';
}
