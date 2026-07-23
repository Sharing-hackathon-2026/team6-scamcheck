import { normalizeNfc } from './unicode.js?v=stage5-tabs-v16';

export const HISTORY_KEY = 'scamcheck.history.v2';
export const HISTORY_LIMIT = 10;

function hasStorageShape(storage) {
  return storage && typeof storage.getItem === 'function' && typeof storage.setItem === 'function';
}

export function sanitizeHistoryEntry(value) {
  if (!value || typeof value !== 'object') return null;
  const text = typeof value.text === 'string' ? normalizeNfc(value.text).trim() : '';
  const detective = value.detective;
  if (!text || !detective || typeof detective !== 'object') return null;
  const psychologist = value.psychologist && typeof value.psychologist === 'object'
    ? value.psychologist
    : null;
  const technicalAnalysis = value.technicalAnalysis && typeof value.technicalAnalysis === 'object'
    ? value.technicalAnalysis
    : null;
  return {
    id: typeof value.id === 'string' && value.id ? value.id : `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    text,
    detective,
    psychologist,
    technicalAnalysis,
    createdAt: Number.isFinite(value.createdAt) ? value.createdAt : Date.now(),
  };
}

export function loadHistory(storage) {
  if (!hasStorageShape(storage)) return [];
  try {
    const parsed = JSON.parse(storage.getItem(HISTORY_KEY) || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed.map(sanitizeHistoryEntry).filter(Boolean).slice(0, HISTORY_LIMIT);
  } catch {
    return [];
  }
}

export function saveHistory(storage, entries) {
  if (!hasStorageShape(storage)) return false;
  try {
    const safeEntries = (Array.isArray(entries) ? entries : [])
      .map(sanitizeHistoryEntry)
      .filter(Boolean)
      .slice(0, HISTORY_LIMIT);
    storage.setItem(HISTORY_KEY, JSON.stringify(safeEntries));
    return true;
  } catch {
    return false;
  }
}

export function addHistoryEntry(entries, {
  text, detective, psychologist = null, technicalAnalysis = null, now = Date.now(), id,
} = {}) {
  const entry = sanitizeHistoryEntry({
    id, text, detective, psychologist, technicalAnalysis, createdAt: now,
  });
  if (!entry) return Array.isArray(entries) ? entries.slice(0, HISTORY_LIMIT) : [];
  const current = Array.isArray(entries) ? entries : [];
  const withoutDuplicate = current.filter((item) => item.text !== entry.text);
  return [entry, ...withoutDuplicate].slice(0, HISTORY_LIMIT);
}

export function deleteHistoryEntry(entries, id) {
  return (Array.isArray(entries) ? entries : []).filter((entry) => entry.id !== id);
}

export function clearHistory() {
  return [];
}
