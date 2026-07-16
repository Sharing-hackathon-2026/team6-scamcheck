# Design reference — Own Your Online / Scam Check

Reference inspected on 2026-07-16:

- Page: <https://www.ownyouronline.govt.nz/personal/scam-check/text/>
- Desktop viewport: 1440×1000; full-page evidence: `/tmp/nz-scamcheck-desktop.png`
- Mobile viewport: 390×844; full-page evidence: `/tmp/nz-scamcheck-mobile.png`
- This document extracts visual principles and measured CSS values. It is **not** permission
  to copy the New Zealand Government logo, wording, illustrations, or proprietary assets.

## 1. Overall art direction

The page feels official without looking bureaucratic: oversized geometric typography, a very
small palette used boldly, broad flat colour fields, generous empty space, and almost no card
chrome. The working content sits on a pale mint canvas while the violet hero and deep-teal
footer create clear beginning/end landmarks.

The strongest reusable principles for ScamCheck are:

1. One task per page; navigation separates related tools.
2. A bold, short hero followed by a narrow, stable reading rail.
3. Flat sequential content instead of a stack of floating cards.
4. Pill navigation and actions, but large content regions use only a few broad curves.
5. Large numbered steps connected by a subtle dotted rule.
6. High-contrast dark teal copy on mint; violet reserved for brand/action emphasis.
7. Left alignment throughout; centred alignment appears only inside a final decision panel.

## 2. Extracted palette

Values below come from the live stylesheet and computed styles.

| Role | Value | Live use |
|---|---:|---|
| Canvas / sky light | `#D6FFF7` | Body and main working area |
| Primary ink / forest | `#1C4650` | Body copy, headings, footer background |
| Forest dark | `#15353C` | Hover/deeper surfaces |
| Forest darker | `#0C1E22` | Strong active states |
| Violet | `#7462E2` | Personal hero, round feature icons |
| Violet dark | `#5838CB` | Hero depth / hover |
| Violet darker | `#4D30B6` | Wave depth, violet-on-white ink |
| Violet light | `#BCB4F2` | Soft accent |
| Violet lightest | `#ECE9FB` | Subtle violet surface |
| Spring green | `#2AC680` | Positive accent |
| Spring light | `#89ECAA` | Positive/secondary surface |
| Sky | `#AAE6DB` | Cool supporting surface |
| Warning | `#FFE100` | Warning emphasis |
| Warning light | `#FFF399` | Soft warning surface |
| Destructive | `#C64A24` | Error/destructive action |
| Destructive lightest | `#FECCBD` | Error surface |
| White | `#FFFFFF` | Hero copy and pill decisions |

### ScamCheck adaptation

Use the reference triad as the new identity:

- Main canvas: mint `#D6FFF7` or a slightly quieter tint where long Vietnamese text needs it.
- Primary ink/action: forest `#1C4650`.
- Brand and selected navigation: violet `#7462E2` / `#4D30B6`.
- Retain semantic danger, warning, safe colours; do not encode all risk states as violet.
- Preserve automatic dark mode and Stage 5 high-contrast mode. Dark mode should translate the
  relationships, not mechanically invert the reference colours.

## 3. Typography

### Measured reference typography

The site declares **Galano Grotesque** at weights 400, 500, 700 and 900.

| Element | Desktop | Mobile | Weight / line-height |
|---|---:|---:|---|
| Hero H1 | `96px` | `62px` | 700 / 1.0 |
| Major section H2 | `58px` | about `41px` | 700 / 1.0 |
| Sequential question | `44px` | about `33px` | 700 / 1.0 |
| Sequential number | `44px` desktop tier | `33px` | 700 / 1.0 |
| Body | `16px` | `16px` | 400 / relaxed |
| Tab | `16px` | `16px` | 700 |

ScamCheck serves Vietnamese adults 45+, so the visual character should be retained while the
minimum body copy remains **18px** and fluid heading sizes avoid the reference site's very large
mobile wrapping.

### Font licensing decision

Galano Grotesque is a commercial typeface. The inspected site self-hosts licensed WOFF2 files;
those files must **not** be copied, scraped, or hotlinked. If the project owner supplies a Galano
webfont licence later, the token stack can place it first. For this repository, use a legally
redistributable Google Fonts geometric sans with full Vietnamese coverage—preferably
**Be Vietnam Pro**—self-hosted with its OFL licence. This preserves the rounded geometric rhythm
and improves Vietnamese diacritics without taking a proprietary asset.

Recommended stack:

```css
font-family: "Be Vietnam Pro", "Galano Grotesque", ui-sans-serif, system-ui, sans-serif;
```

## 4. Layout and alignment

### Desktop measurements (1440px viewport)

- Hero: `1440 × 600px`, `padding-top: 120px`, bottom corners `64px`.
- Main content begins after `128px` vertical separation.
- Sequential reading rail: `860px` wide, centred at `x=290`.
- Main page gutter reaches `64px` at large desktop.
- Tabs are left-aligned to the reading rail; selected tab measured `86.36 × 48px` with
  `12px 24px` padding.
- Three sequential rows measured approximately `221px`, `221px`, `157px`; first two use `64px`
  bottom spacing.
- Footer: `425px` tall in the reference capture, `80px` vertical padding, `64px` top corners.

### Mobile measurements (390px viewport)

- Horizontal content gutter: `24px`.
- Hero H1 starts at `x=24`; hero content remains left-aligned.
- Hero ends around `596px`; large artwork is cropped rather than scaled into clutter.
- Tabs form a horizontally scrollable, single-line pill rail. The content itself has no
  horizontal page overflow.
- Sequential rows use a narrow number column and copy column. Questions wrap naturally; body
  copy stays left-aligned.
- Footer becomes a single vertical information rail with broad rounded top corners.

### ScamCheck information architecture

Use three primary destinations in a consistent tab-like global navigation:

1. **Kiểm tra lừa đảo** — `/` — message input, result, rescue flow, share card, recent checks.
2. **Thư viện** — `/library.html` — filters and 12 scam patterns only.
3. **Luyện tập** — `/practice.html` — 10-question quiz only.

Do not render the library on the check page. Navigation must use real links so each destination
has a URL, works without client-side routing, exposes the current page via `aria-current="page"`,
and supports open-in-new-tab/back/forward.

## 5. Shape language

- Hero: broad full-width surface with large `48–64px` lower corner radius.
- Footer: inverse broad surface with matching `48–64px` upper radius.
- Tabs/buttons: true pills (`999px`).
- Working input/results: controlled `16–24px` radii; avoid every section looking like an equal
  floating card.
- Use flat section dividers and background bands before adding more containers.
- Reference has almost no shadow. ScamCheck should use borders, colour contrast and at most a
  restrained short shadow; no blurred SaaS card cloud.

## 6. Sequential pattern

The reference's strongest utility motif is a numbered sequence:

- `01`, `02`, `03` in bold dark teal.
- Number is absolutely positioned in a dedicated left column, not an icon circle.
- A `1px` dashed low-opacity forest line connects steps.
- Desktop question and explanation align to a stable copy rail.
- Mobile preserves the two-column number/copy relationship.

Adapt this for rescue steps and quiz progress where it improves comprehension. Do not force it
onto unrelated data such as warning tags or hotline metadata.

## 7. Navigation and controls

- Desktop has quiet text navigation integrated into the hero; active context remains visible.
- Mobile collapses the large institutional nav. ScamCheck follows that behavior with an
  accessible hamburger button opening the same three real links in a vertical menu; desktop
  keeps the pill tab rail visible.
- Reference tablist border: `1px solid rgba(28,70,80,.24)`.
- Selected tab: forest background, white text, `2px` forest border, 48px height.
- Unselected tab: transparent, forest text, same geometry.
- Decision panel: deep forest surface, white heading, two white pill actions with violet text.
- Minimum ScamCheck touch target remains 44×44px; primary actions should be 52–56px tall.

## 8. Hero and decorative treatment

Reference hero layers violet/cobalt wave SVGs on a violet field. For ScamCheck:

- Recreate the **idea**, not the asset: CSS/SVG-authored abstract arcs owned by this project.
- Keep arcs behind text, with low detail and no generic gradient blobs.
- Use no stock illustration, government logo, or copied wave path.
- Hero copy should be short and task-specific. The actual form begins immediately after the
  hero rather than being embedded in decorative overlap.

## 9. Icons

The requested family is **Google Material Icons / Material Symbols Rounded**.

- Use one family and one optical weight throughout.
- Sizes: 18px inline, 24px controls, 32px feature/status.
- Align inline icons with `vertical-align: -0.125em`.
- Prefer specific symbols: `fact_check`, `menu_book`, `quiz`, `mic`, `delete`, `contrast`,
  `text_increase`, `history`, `shield`, `warning`, `call`, `share`, `download`.
- Decorative emoji and mixed hand-drawn SVG icon families are prohibited.
- Prefer a self-hosted Google icon font plus its licence so core controls do not depend on a
  third-party request. If the icon font fails, accessible text/`aria-label` must still explain
  every control.

## 10. Accessibility adaptations

The reference site's 16px body is too small for the target audience. ScamCheck must retain:

- Body copy ≥18px at 100%.
- Existing 100/115/130% text controls and high-contrast preference.
- Automatic `prefers-color-scheme` dark mode.
- AA contrast in every theme/preference combination.
- Visible 3px focus treatment.
- Minimum 44px targets and no hover-only operation.
- Reduced-motion handling.
- Real semantic links for primary tabs and real buttons for actions.
- No horizontal page overflow at 320px; the mobile navigation opens vertically instead of
  creating a horizontally scrolling page.

## 11. What not to copy

- New Zealand Government/NCSC/Own Your Online logos or lockups.
- Māori/English copy, organisation names or footer structure.
- Their wave SVG files, font binaries, social icons or campaign assets.
- Their exact page composition where it conflicts with ScamCheck's AI result/rescue workflow.

The target is an original Vietnamese ScamCheck interface informed by the reference's spacing,
confidence, typography, palette relationships and one-task-per-page architecture.
