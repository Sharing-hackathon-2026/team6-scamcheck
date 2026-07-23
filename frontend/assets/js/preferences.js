// Tùy chọn hiển thị: tương phản cao + cỡ chữ (Stage 5, L5-10).
// Phần pure (normalize/load/save) không phụ thuộc DOM để có thể test bằng node:test.
// Phần wire/apply chạm DOM nhưng chỉ chạy khi được gọi — không khởi tạo module-level.

export const PREF_KEY = 'scamcheck.prefs.v1';
export const DEFAULT_PREFERENCES = Object.freeze({ highContrast: false, fontScale: '1' });

/** Ba mức cỡ chữ trong dropdown: 100% / 115% / 130%. */
export const FONT_SCALE_OPTIONS = Object.freeze(['1', '1.15', '1.3']);

const FONT_TRANSITION_MS = 300;
const fontTransitionTimers = new WeakMap();

const FONT_SCALE_LABELS = Object.freeze({
  '1': '100%',
  '1.15': '115%',
  '1.3': '130%',
});

export function fontScaleLabel(value) {
  return FONT_SCALE_LABELS[value] || '100%';
}

function hasStorageShape(storage) {
  return Boolean(storage)
    && typeof storage.getItem === 'function'
    && typeof storage.setItem === 'function';
}

/** Ép dữ liệu thô (từ localStorage hoặc đầu vào lạ) về dạng an toàn. */
export function normalizePreferences(value) {
  const fallback = { ...DEFAULT_PREFERENCES };
  if (!value || typeof value !== 'object') return fallback;
  const fontScale = FONT_SCALE_OPTIONS.includes(value.fontScale) ? value.fontScale : DEFAULT_PREFERENCES.fontScale;
  return {
    highContrast: value.highContrast === true,
    fontScale,
  };
}

/** Đọc tùy chọn; không bao giờ ném — localStorage thiếu/hỏng vẫn dùng được. */
export function loadPreferences(storage) {
  if (!hasStorageShape(storage)) return { ...DEFAULT_PREFERENCES };
  try {
    const parsed = JSON.parse(storage.getItem(PREF_KEY) || 'null');
    return normalizePreferences(parsed);
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

/** Ghi tùy chọn; trả về true nếu lưu được, false nếu storage không sẵn sàng. */
export function savePreferences(storage, preferences) {
  if (!hasStorageShape(storage)) return false;
  try {
    storage.setItem(PREF_KEY, JSON.stringify(normalizePreferences(preferences)));
    return true;
  } catch {
    return false;
  }
}

/**
 * Áp dụng tùy chọn lên phần tử gốc (thường là document.documentElement).
 * Tách ra để app.js và practice.js dùng chung; không unit test trực tiếp (cần DOM).
 */
export function applyPreferences(root, preferences, { animateFont = false } = {}) {
  if (!root || typeof root.setAttribute !== 'function') return;
  const prefs = normalizePreferences(preferences);
  if (prefs.highContrast) {
    root.setAttribute('data-high-contrast', 'true');
  } else {
    root.removeAttribute('data-high-contrast');
  }

  const view = root.ownerDocument?.defaultView;
  const reduceMotion = view?.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;
  if (animateFont && !reduceMotion && root.classList) {
    const oldTimer = fontTransitionTimers.get(root);
    if (oldTimer) clearTimeout(oldTimer);
    root.classList.remove('is-font-resizing');
    // Buộc browser ghi nhận cỡ cũ trước khi đổi custom property.
    void root.offsetWidth;
    root.classList.add('is-font-resizing');
    const timer = setTimeout(() => {
      root.classList.remove('is-font-resizing');
      fontTransitionTimers.delete(root);
    }, FONT_TRANSITION_MS);
    fontTransitionTimers.set(root, timer);
  }
  root.style.setProperty('--app-font-scale', prefs.fontScale);
}

/**
 * Lắp điều khiển hiển thị vào một vùng DOM chứa:
 *  - nút [data-pref="contrast"] (bật/tắt tương phản cao)
 *  - dropdown native [data-font-scale]
 * Trả về { getPreferences } để các luồng khác biết trạng thái hiện tại.
 */
export function wirePreferences({
  root,
  storage = (typeof localStorage !== 'undefined' ? localStorage : null),
  documentRoot = (typeof document !== 'undefined' ? document.documentElement : null),
  initial,
}) {
  let prefs = initial ? normalizePreferences(initial) : loadPreferences(storage);
  const contrastBtn = root && root.querySelector ? root.querySelector('[data-pref="contrast"]') : null;
  const scaleSelect = root && root.querySelector ? root.querySelector('[data-font-scale]') : null;
  const status = root && root.querySelector ? root.querySelector('[data-pref-status]') : null;

  const sync = () => {
    if (contrastBtn) contrastBtn.setAttribute('aria-pressed', String(prefs.highContrast));
    if (scaleSelect) scaleSelect.value = prefs.fontScale;
  };

  const commit = ({ animateFont = false } = {}) => {
    savePreferences(storage, prefs);
    applyPreferences(documentRoot, prefs, { animateFont });
    sync();
  };

  commit();

  if (root && typeof root.addEventListener === 'function') {
    root.addEventListener('click', (event) => {
      const contrast = event.target.closest('[data-pref="contrast"]');
      if (contrast) {
        prefs = normalizePreferences({ ...prefs, highContrast: !prefs.highContrast });
        commit();
        if (status) status.textContent = prefs.highContrast
          ? 'Đã bật tương phản cao.'
          : 'Đã tắt tương phản cao.';
        return;
      }
    });
    root.addEventListener('change', (event) => {
      const select = event.target.closest('[data-font-scale]');
      if (!select || !FONT_SCALE_OPTIONS.includes(select.value)) return;
      prefs = normalizePreferences({ ...prefs, fontScale: select.value });
      commit({ animateFont: true });
      if (status) status.textContent = `Đã đổi cỡ chữ thành ${fontScaleLabel(prefs.fontScale)}.`;
    });
  }

  return { getPreferences: () => ({ ...prefs }) };
}
