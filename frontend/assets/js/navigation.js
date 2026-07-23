// Điều hướng dùng real links. Trên desktop hiển thị tab rail; trên màn hình
// hẹp chuyển thành menu dọc có nút hamburger, hỗ trợ Escape và click ra ngoài.
// Các tab vẫn là real links; HTML đích được warm-up theo tương tác, còn CSS/JS/
// font/icon dùng chung được HTTP cache immutable nên không tải lại giữa các trang.

const prefetchedPages = new Set();
const VIEWPORT_EFFECT_DELAY_MS = 90;
const VIEWPORT_EFFECT_DURATION_MS = 260;

/** Nhịp zoom nhẹ sau khi người dùng kết thúc kéo rộng/hẹp cửa sổ. */
export function wireViewportResizeEffect(
  view = globalThis.window,
  root = globalThis.document?.documentElement,
) {
  if (!view?.addEventListener || !root?.classList) return false;
  let previousWidth = view.innerWidth;
  let pendingClass = '';
  let debounceTimer;
  let cleanupTimer;

  const clearClasses = () => {
    root.classList.remove('viewport-zoom-in', 'viewport-zoom-out');
  };
  view.addEventListener('resize', () => {
    const nextWidth = view.innerWidth;
    if (Math.abs(nextWidth - previousWidth) >= 2) {
      pendingClass = nextWidth > previousWidth ? 'viewport-zoom-in' : 'viewport-zoom-out';
    }
    previousWidth = nextWidth;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const effectClass = pendingClass;
      pendingClass = '';
      if (!effectClass || view.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
      clearClasses();
      void root.offsetWidth;
      root.classList.add(effectClass);
      clearTimeout(cleanupTimer);
      cleanupTimer = setTimeout(clearClasses, VIEWPORT_EFFECT_DURATION_MS);
    }, VIEWPORT_EFFECT_DELAY_MS);
  });
  return true;
}

export function prefetchPage(href, doc = globalThis.document, currentHref = globalThis.location?.href) {
  if (!href || !doc?.head || typeof URL !== 'function') return false;
  let target;
  try {
    target = new URL(href, currentHref);
  } catch {
    return false;
  }
  const current = currentHref ? new URL(currentHref) : null;
  if (!current || target.origin !== current.origin || target.href === current.href) return false;
  if (prefetchedPages.has(target.href)) return true;
  const link = doc.createElement('link');
  link.rel = 'prefetch';
  link.as = 'document';
  link.href = target.href;
  doc.head.append(link);
  prefetchedPages.add(target.href);
  return true;
}

export function wireTabPrefetch(rail, doc = globalThis.document) {
  if (!rail || typeof rail.addEventListener !== 'function') return false;
  const warm = (event) => {
    const anchor = event.target?.closest?.('a[href]');
    if (anchor) prefetchPage(anchor.href, doc);
  };
  rail.addEventListener('pointerenter', warm, true);
  rail.addEventListener('focusin', warm);
  rail.addEventListener('touchstart', warm, { passive: true });
  rail.setAttribute?.('data-prefetch-ready', 'true');
  return true;
}

export function revealCurrentTab(rail) {
  if (!rail || typeof rail.querySelector !== 'function') return false;
  const current = rail.querySelector('[aria-current="page"]');
  if (!current || typeof rail.scrollTo !== 'function') return false;
  const maxScroll = Math.max(0, rail.scrollWidth - rail.clientWidth);
  if (maxScroll === 0) return true;
  const target = Math.min(
    maxScroll,
    Math.max(0, current.offsetLeft - ((rail.clientWidth - current.offsetWidth) / 2)),
  );
  rail.scrollTo({ left: target, behavior: 'auto' });
  return true;
}

export function setMobileMenuOpen(toggle, rail, open) {
  if (!toggle || !rail) return false;
  const isOpen = Boolean(open);
  toggle.setAttribute('aria-expanded', String(isOpen));
  toggle.setAttribute('aria-label', isOpen ? 'Đóng trình đơn chính' : 'Mở trình đơn chính');
  if (isOpen) rail.setAttribute('data-open', 'true');
  else rail.removeAttribute('data-open');
  return isOpen;
}

export function wireMobileMenu(header) {
  if (!header || typeof header.querySelector !== 'function') return false;
  const toggle = header.querySelector('.mobile-menu-toggle');
  const rail = header.querySelector('.tab-rail');
  if (!toggle || !rail) return false;

  header.setAttribute('data-mobile-menu-ready', 'true');
  setMobileMenuOpen(toggle, rail, false);

  toggle.addEventListener('click', () => {
    setMobileMenuOpen(toggle, rail, toggle.getAttribute('aria-expanded') !== 'true');
  });
  rail.addEventListener('click', (event) => {
    if (event.target.closest('a')) setMobileMenuOpen(toggle, rail, false);
  });
  document.addEventListener('click', (event) => {
    if (!header.contains(event.target)) setMobileMenuOpen(toggle, rail, false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || toggle.getAttribute('aria-expanded') !== 'true') return;
    setMobileMenuOpen(toggle, rail, false);
    toggle.focus();
  });
  window.addEventListener('resize', () => {
    if (window.innerWidth > 700) setMobileMenuOpen(toggle, rail, false);
  });
  return true;
}

if (typeof document !== 'undefined') {
  const rail = document.querySelector('.tab-rail');
  const header = document.querySelector('.app-bar');
  if (rail) {
    const reveal = () => revealCurrentTab(rail);
    window.requestAnimationFrame(reveal);
    window.addEventListener('load', reveal, { once: true });
    if (document.fonts?.ready) document.fonts.ready.then(reveal).catch(() => {});
  }
  wireMobileMenu(header);
  wireTabPrefetch(rail);
  wireViewportResizeEffect(window, document.documentElement);
}
