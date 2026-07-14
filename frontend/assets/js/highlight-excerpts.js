/**
 * Chuẩn hoá chuỗi để đối chiếu excerpt thân thiện với hoa/thường và khoảng trắng.
 * Mảng map giữ vị trí từng ký tự đã chuẩn hoá trong chuỗi gốc.
 */
export function normalizeWithMap(value, locale = 'vi') {
  const source = String(value ?? '');
  let normalized = '';
  const map = [];
  let pendingWhitespace = false;

  for (let index = 0; index < source.length;) {
    const codePoint = source.codePointAt(index);
    const character = String.fromCodePoint(codePoint);
    const width = character.length;

    if (/\s/u.test(character)) {
      pendingWhitespace = normalized.length > 0;
      index += width;
      continue;
    }

    if (pendingWhitespace) {
      normalized += ' ';
      map.push(index);
      pendingWhitespace = false;
    }

    const folded = character.toLocaleLowerCase(locale);
    for (const foldedCharacter of folded) {
      normalized += foldedCharacter;
      map.push(index);
    }
    index += width;
  }

  return { normalized, map };
}

function findAllRanges(source, excerpt, locale) {
  const sourceNormalized = normalizeWithMap(source, locale);
  const excerptNormalized = normalizeWithMap(excerpt, locale).normalized.trim();
  if (!excerptNormalized) return [];

  const ranges = [];
  let fromIndex = 0;
  while (fromIndex <= sourceNormalized.normalized.length - excerptNormalized.length) {
    const foundAt = sourceNormalized.normalized.indexOf(excerptNormalized, fromIndex);
    if (foundAt === -1) break;

    const start = sourceNormalized.map[foundAt];
    const lastMappedIndex = sourceNormalized.map[foundAt + excerptNormalized.length - 1];
    const lastCodePoint = source.codePointAt(lastMappedIndex);
    const end = lastMappedIndex + String.fromCodePoint(lastCodePoint).length;
    ranges.push({ start, end });
    fromIndex = foundAt + Math.max(1, excerptNormalized.length);
  }
  return ranges;
}

/**
 * Tìm và hợp nhất các khoảng excerpt trong bản tin gốc.
 * - Không phân biệt hoa/thường theo locale Việt.
 * - Chuỗi khoảng trắng liên tiếp được xem như một khoảng trắng.
 * - Nhiều excerpt trùng/overlap được hợp nhất để không tạo mark lồng nhau.
 * - Excerpt không tồn tại bị bỏ qua.
 */
export function findExcerptRanges(source, excerpts, { locale = 'vi' } = {}) {
  const text = String(source ?? '');
  if (!text || !Array.isArray(excerpts)) return [];

  const ranges = excerpts
    .flatMap((excerpt) => findAllRanges(text, excerpt, locale))
    .sort((a, b) => a.start - b.start || a.end - b.end);

  return ranges.reduce((merged, range) => {
    const previous = merged.at(-1);
    if (!previous || range.start > previous.end) {
      merged.push({ ...range });
    } else {
      previous.end = Math.max(previous.end, range.end);
    }
    return merged;
  }, []);
}

/** Trả các đoạn text/mark thuần dữ liệu để render bằng textContent (an toàn XSS). */
export function buildHighlightedSegments(source, excerpts, options) {
  const text = String(source ?? '');
  const ranges = findExcerptRanges(text, excerpts, options);
  if (!ranges.length) return text ? [{ text, highlighted: false }] : [];

  const segments = [];
  let cursor = 0;
  ranges.forEach(({ start, end }) => {
    if (start > cursor) segments.push({ text: text.slice(cursor, start), highlighted: false });
    segments.push({ text: text.slice(start, end), highlighted: true });
    cursor = end;
  });
  if (cursor < text.length) segments.push({ text: text.slice(cursor), highlighted: false });
  return segments;
}

/** Render vào DOM mà không dùng innerHTML. */
export function renderHighlightedText(container, source, excerpts, documentRef = document) {
  const fragment = documentRef.createDocumentFragment();
  buildHighlightedSegments(source, excerpts).forEach((segment) => {
    const node = segment.highlighted
      ? documentRef.createElement('mark')
      : documentRef.createTextNode(segment.text);
    if (segment.highlighted) node.textContent = segment.text;
    fragment.append(node);
  });
  container.replaceChildren(fragment);
}
