// Điều hướng dùng real links. Trên desktop hiển thị tab rail; trên màn hình
// hẹp chuyển thành menu dọc có nút hamburger, hỗ trợ Escape và click ra ngoài.

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
}
