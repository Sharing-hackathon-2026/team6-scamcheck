import { normalizeNfc } from './unicode.js?v=stage5-tabs-v16';

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

function searchableText(value) {
  return normalizeNfc(String(value || ''))
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLocaleLowerCase('vi')
    .replace(/\s+/g, ' ')
    .trim();
}

export function filterLibraryItems(items, group = 'all', query = '', groups = []) {
  const source = Array.isArray(items) ? items : [];
  const grouped = group === 'all' ? source : source.filter((item) => item?.group === group);
  const needle = searchableText(query);
  if (!needle) return grouped;
  const groupLabels = new Map(
    (Array.isArray(groups) ? groups : []).map((item) => [item?.key, item?.label]),
  );
  return grouped.filter((item) => searchableText([
    groupLabels.get(item?.group),
    item?.title,
    item?.summary,
    item?.safe_action,
    ...(Array.isArray(item?.warning_signs) ? item.warning_signs : []),
  ].join(' ')).includes(needle));
}

export function libraryGroupFromHash(hash, validGroups) {
  const key = String(hash || '').replace(/^#/, '');
  return Array.isArray(validGroups) && validGroups.includes(key) ? key : 'all';
}
