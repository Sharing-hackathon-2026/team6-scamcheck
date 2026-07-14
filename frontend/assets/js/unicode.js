export function normalizeNfc(value) {
  return typeof value === 'string' ? value.normalize('NFC') : value;
}
