// Material Symbols Rounded — single self-hosted icon family.
// The font is subsetted to ScamCheck's glyphs and referenced by codepoint
// (PUA) so it never depends on ligature shaping. Each entry maps an icon
// name to its Unicode codepoint character. Use materialIcon() to build an
// accessible <span>; never put icon glyphs in innerHTML.

export const MATERIAL_ICONS = Object.freeze({
  shield: "\ue9e0",
  fact_check: "\uf0c5",
  menu_book: "\uea19",
  quiz: "\uf04c",
  mic: "\ue31d",
  delete: "\ue92e",
  contrast: "\ueb37",
  text_increase: "\ueae2",
  history: "\ue8b3",
  warning: "\uf083",
  call: "\uf0d4",
  sms: "\ue625",
  share: "\ue80d",
  download: "\uf090",
  check_circle: "\uf0be",
  expand_more: "\ue5cf",
  refresh: "\ue5d5",
  error: "\uf8b6",
  verified: "\uef76",
  close: "\ue5cd",
  support_agent: "\uf0e2",
  lightbulb: "\ue90f",
  arrow_forward: "\ue5c8",
  key: "\ue73c",
  link: "\ue250",
  rule: "\uf1c2",
  priority_high: "\ue645",
  home: "\ue9b2",
  arrow_back: "\ue5c4",
  search: "\uef7a",
  block: "\uf08c",
  info: "\ue88e",
  gpp_good: "\uf013",
  emergency: "\ue1eb",
  lock: "\ue899",
  campaign: "\uef49",
  report: "\uf052",
  cancel: "\ue888",
  chevron_right: "\ue5cc",
});

/**
 * Build an accessible icon <span>. By default decorative (aria-hidden);
 * pass `label` for an icon-only control so assistive tech announces it.
 */
export function materialIcon(name, { className = "", label = "" } = {}) {
  const span = document.createElement("span");
  span.className = `msymbols${className ? ` ${className}` : ""}`;
  span.textContent = MATERIAL_ICONS[name] ?? "";
  if (label) {
    span.setAttribute("role", "img");
    span.setAttribute("aria-label", label);
  } else {
    span.setAttribute("aria-hidden", "true");
  }
  return span;
}

/** Codepoint character only — for places that compose text safely. */
export function iconChar(name) {
  return MATERIAL_ICONS[name] ?? "";
}
