# LearnQuest Design Guidelines

**Status:** authoritative for all frontend work.
**Applies to:** everything under `frontend/src/`.
**Read this before building any page or component.**

LearnQuest is a **dark-first, editorial, information-dense** product surface. A
near-black canvas, panels lifted by a single hairline border, an editorial serif
for display type against a neutral UI face, and exactly one accent colour. The
chrome should recede so the content — problems, explanations, progress, data —
is what the eye lands on.

If a screen looks like a consumer game, or like a generic admin template, it is
wrong for this product.

---

## 0. Non-negotiables

These three exist because breaking them is what made the UI look assembled
rather than designed. Reviewers should reject a PR that violates any of them.

1. **Never write a raw colour.** No `bg-white`, no `text-slate-500`, no
   `#1A1E26`. Only tokens: `bg-surface`, `text-muted`, `border-line`. In
   September 2026 there were 429 hardcoded palette classes across 16 files, each
   picking a slightly different grey for the same job; they were all replaced
   with tokens in one pass. Do not start the drift again.
2. **Never write a `dark:` variant.** The theme lives in CSS variables on
   `:root` in `index.css`, so `.dark` is never applied and a `dark:` utility is
   dead code that looks meaningful.
3. **Never hand-roll a control.** Use `Button`, `Input`, `Select`, `Badge`,
   `Card` from `components/ui`. A bespoke `<button className="px-2 py-1">` is
   how a design system dies.

---

## 1. The five rules

1. **Depth comes from a border and a level change, not a shadow.** Three surface
   levels and no more: `canvas` (the page) -> `surface` (a panel) -> `raised` (a
   panel on a panel). On a near-black canvas a drop shadow is invisible, so
   stacking shadows only adds mud. Shadows are for things that genuinely float
   (dropdowns, modals).
2. **Dense, but readable.** Body text is **15px**, tables 15px, micro-labels
   12px. Nothing in the product is smaller than 12px. The previous system ran a
   14px body with 13px navigation and 11px chips, which is below what anyone
   should be asked to read on a laptop at arm's length.
3. **Controls are 40px.** `Button` `md` is 40px tall and `.field` matches it. A
   form where the input is shorter than the button beside it always looks
   broken. `sm` (36px) is for toolbars and table rows; `lg` (48px) is for a
   single hero action.
4. **Colour means status, never decoration.** Green = easy/passing.
   Amber = medium/warning. Red = hard/failing. Violet = the one primary action,
   active navigation, and the tutor. Everything else is neutral.
5. **Two faces, two jobs.** `font-display` (Instrument Serif) for page titles
   and hero copy only. `font-sans` (Inter) for all UI. `font-mono` (JetBrains
   Mono) for micro-labels, topic tags and code. An editorial serif against a
   neutral sans is most of what separates this from a dashboard template — do
   not use the serif for body copy, and never for a button.

---

## 2. Tokens

All tokens live in `frontend/tailwind.config.js`. **Use token names, never raw hex.**

### Colour

| Token | Hex | Use for |
|---|---|---|
| `primary-600` | `#7C3AED` | The one primary action per view, active nav |
| `primary-700` | `#6D28D9` | Hover / pressed |
| `easy` | `#00AF54` | Easy difficulty, passing, solved |
| `medium` | `#FFB300` | Medium difficulty, warnings |
| `hard` | `#E5384B` | Hard difficulty, failures, destructive |
| `info` | `#2D7FF9` | Informational callouts |
| `ink` | `#1F2933` | Headings |
| `body` | `#39424E` | Body copy |
| `muted` | `#6B7885` | Secondary text, table headers |
| `faint` | `#9AA5B1` | Placeholders, disabled |
| `line` | `#E4E7EB` | The 1px hairline border |
| `line-strong` | `#CBD2D9` | Input borders, dividers that must read |
| `surface` | `#FFFFFF` | Cards, tables, panels |
| `canvas` | `#F5F7FA` | Page background |

Each difficulty has `-bg` and `-fg` variants for tinted chips:
`bg-easy-bg text-easy-fg`.

### Type

**Inter** for UI, **JetBrains Mono** for code. Loaded in `frontend/index.html`.

| Role | Classes |
|---|---|
| Page title | `text-2xl font-semibold text-ink` |
| Section heading | `text-lg font-semibold` |
| Card title | `text-base font-semibold` |
| Body | *(default — 14px)* |
| Table / dense text | `text-sm` (13px) |
| Secondary | `text-sm text-muted` |
| Label / table header | `.label` (11px, uppercase, muted) |

### Shape and spacing

- Radius: `rounded` (4px) default, `rounded-lg` (6px) cards, `rounded-pill` chips only.
- Border: **1px** (`border border-line`). The Tailwind default is 1px, so a bare
  `border` is correct.
- Spacing: 4px scale. Cards `p-4`. Sections `py-6` to `py-8`. Keep it tight.

---

## 3. Components

**Always import from `components/ui/`. Never hand-roll a button.**

### Button
```jsx
<Button variant="primary" size="md">Submit</Button>
```
Flat, 32px tall at `md`. Variants: `primary`, `secondary`, `success`, `danger`,
`ghost`, `link`. **One primary per view** — everything else is `secondary` or `ghost`.

### Card
```jsx
<Card>…</Card>
```
1px border, no shadow. `CardHeader` adds a titled header with a divider.

### Tables — the backbone of this UI
Use the `.table-dense` class for problem lists, course lists, leaderboards:
```jsx
<table className="table-dense">
```
13px, 1px row separators, uppercase muted headers. Prefer a table over a grid of
cards whenever the rows share the same columns.

### Badge / chips
`<Badge tone="easy|medium|hard|info|primary|neutral">`. Tinted text on a light
background — never a heavy solid block.

### Inputs
`Input` / `Select`, or the `.field` class. 1px border, 2px focus ring.

---

## 4. Layout and navigation

- **Desktop:** top bar (brand, streak/XP, profile) + 192px left rail.
- **Mobile:** bottom tab bar with the five main destinations.
- Max content width `1400px` — this is a data UI, use the screen.
- Page content is wrapped by `AppLayout`; pages render their own `PageHeader`.

**Never add a nav link to a route that does not exist yet** — it 404s. There's a
note in `AppLayout.jsx` marking where `/practice` goes once it ships.

### Heights must not depend on width

A real bug we shipped: a panel used `aspect-square`, so its height tracked its
width and the column grew to 1176px on wide screens. **Do not derive a layout
height from an aspect ratio.** Pin heights, or let flex/grid distribute them, and
cap aspect-ratio boxes with `max-w-*`.

---

## 5. Motion

Minimal. `animate-fade-in` (150ms) for panels appearing, `animate-shimmer` for
skeletons. That is the whole vocabulary. No bouncing, no celebration animations.

**Never animate React state at 60fps.** We shipped a bug where the avatar called
`setState` on every animation frame, re-rendering a complex SVG 60×/sec. Drive
continuous animation with CSS, or only `setState` when the value actually changes.

---

## 6. Accessibility

Contrast ≥ 4.5:1 for normal text. Measured (WCAG 2.1), so you don't have to guess:

| Combination | Ratio | |
|---|---|---|
| `ink` `#1F2933` on white | 14.76 | ✅ |
| `body` `#39424E` on white | 10.18 | ✅ |
| `body` on `canvas` `#F5F7FA` | 9.48 | ✅ |
| `hard-fg` on `hard-bg` chip | 6.65 | ✅ |
| `info-fg` on `info-bg` chip | 5.76 | ✅ |
| white on `primary-600` (buttons) | 5.70 | ✅ |
| `easy-fg` on `easy-bg` chip | 5.58 | ✅ |
| `medium-fg` on `medium-bg` chip | 5.15 | ✅ |
| `muted` `#6B7885` on white | 4.52 | ✅ *(only just)* |
| **`faint` `#9AA5B1` on white** | **2.50** | ❌ **fails** |

Every colour pair in the system passes AA **except `faint`** — use it for
placeholders and disabled states only, never for real content. `muted` clears
the bar by 0.02, so don't darken the background behind it.
- Focus rings are `ring-2 ring-primary-500/50` and must stay visible.
- Colour is never the only signal. A difficulty chip carries the *word*
  "Easy", not just green.
- Every icon-only button needs `aria-label` or `sr-only` text.
- Re-measure when you add a colour. Do not eyeball it.

---

## 7. Voice and copy

- Plain, direct, second person: "You solved 12 of 40 problems."
- Buttons are verbs: **Submit**, **Run**, **Start**, **Save**.
- Sentence case everywhere. UPPERCASE only for `.label` and table headers.
- No exclamation marks in system text.

---

## 8. Checklist before a PR

- [ ] Imported from `components/ui/` rather than styling a raw element
- [ ] Token names only (`text-muted`, `border-line`) — no raw hex
- [ ] Used a `.table-dense` table where rows share columns
- [ ] One primary button on the view
- [ ] Works at 375px, 768px and 1280px
- [ ] Dark mode checked (`dark:` variants present)
- [ ] Focus visible; icon-only buttons labelled
- [ ] No nav link to a route that doesn't exist
- [ ] No layout height derived from width
- [ ] No `setState` inside a `requestAnimationFrame` loop
- [ ] `npx vite build` passes

---

## 9. Where things live

| Path | What |
|---|---|
| `frontend/tailwind.config.js` | Tokens. **Shared file — change by agreement (plan.md 2.4)** |
| `frontend/src/index.css` | Base layer + `.card`, `.field`, `.chip`, `.label`, `.table-dense` |
| `frontend/src/components/ui/` | The component kit. Extend here, not per-page |
| `frontend/src/components/layout/` | `AppLayout` (bar + rail), `PageHeader` |
| `frontend/index.html` | Inter + JetBrains Mono loading |

Changing a token changes every screen. If a change only suits one page, it
belongs in that page.

---

## Appendix — history

**2026-09-22 — dark-first rebuild.** The light HackerRank-style system was
replaced. What changed and why:

- **Colour moved to CSS variables** (`rgb(var(--x) / <alpha-value>)`), so the
  whole palette swaps from one place and Tailwind's opacity modifiers still
  work. The previous system hardcoded dark values inline in ~40 places with no
  token behind them, which is why nothing matched.
- **Type scale raised.** Body 14px -> 15px; the floor moved from 11px to 12px.
- **Controls raised.** Default button 32px -> 40px; `.field` now matches it.
- **Shell rebuilt.** The nav used to sit inside a 1400px centred container with
  a 16px gutter, leaving ~260px of dead margin each side at 1920 while the
  content felt cramped. The sidebar is now anchored to the viewport edge and
  content uses `.shell` (1600px, gutters that grow with the viewport).
- **Display serif added** (Instrument Serif) for page titles and hero copy.
- **429 hardcoded palette classes** across 16 files were mapped onto tokens, and
  every `dark:` variant was deleted.



The project previously used a playful, Duolingo-style system (Nunito, chunky 3D
buttons, 2px borders, heavy weights). It was replaced in full on 2026-09-21 with
this professional system at the faculty's request. If you find a component with
`btn3d`, `rounded-2xl`, `font-extrabold` or the `eel`/`wolf`/`swan` colour names,
it was missed in the migration — bring it in line with this document.
