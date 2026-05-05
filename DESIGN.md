---
name: Zentri
description: Privacy-first personal financial OS — clear, composed, precision over decoration.
colors:
  # Monochrome chrome palette (light)
  body-bg: "oklch(0.95 0 0)"
  card-surface: "oklch(1 0 0)"
  ink-dark: "oklch(0.11 0 0)"
  quiet-text: "oklch(0.48 0 0)"
  muted-surface: "oklch(0.93 0 0)"
  border: "oklch(0.88 0 0)"
  # Monochrome chrome palette (dark)
  dark-body-bg: "oklch(0 0 0)"
  dark-card-surface: "oklch(0.13 0 0)"
  dark-foreground: "oklch(0.97 0 0)"
  dark-quiet-text: "oklch(0.60 0 0)"
  dark-border: "oklch(1 0 0 / 10%)"
  # Data-driven accents (signals only — never chrome)
  signal-green-bg: "oklch(0.95 0.05 145 / 15%)"
  signal-green-text: "oklch(0.35 0.10 145)"
  signal-amber-bg: "oklch(0.96 0.06 80 / 15%)"
  signal-amber-text: "oklch(0.50 0.10 75)"
  alert-red: "oklch(0.577 0.245 27.325)"
  # Chart ramp (achromatic)
  chart-1: "oklch(0.87 0 0)"
  chart-2: "oklch(0.72 0 0)"
  chart-3: "oklch(0.556 0 0)"
  chart-4: "oklch(0.439 0 0)"
  chart-5: "oklch(0.269 0 0)"
typography:
  display:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "clamp(1.75rem, 3vw, 2.5rem)"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 500
    lineHeight: 1.4
  body:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.01em"
  mono:
    fontFamily: "Geist Mono, Consolas, monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
glass:
  # Light mode
  light-bg: "oklch(1 0 0 / 65%)"
  light-blur: "32px"
  light-saturate: "180%"
  light-border: "oklch(0.11 0 0 / 8%)"
  light-specular: "oklch(1 0 0 / 70%)"
  # Dark mode
  dark-bg: "oklch(1 0 0 / 7%)"
  dark-blur: "32px"
  dark-saturate: "200%"
  dark-border: "oklch(1 0 0 / 12%)"
  dark-specular: "oklch(1 0 0 / 18%)"
rounded:
  xs: "0.375rem"
  sm: "0.5rem"
  md: "0.625rem"
  lg: "0.875rem"
  xl: "1.125rem"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
components:
  button-primary:
    backgroundColor: "oklch(0.11 0 0)"
    textColor: "oklch(1 0 0)"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "32px"
  button-primary-dark:
    backgroundColor: "oklch(0.97 0 0)"
    textColor: "oklch(0.09 0 0)"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "32px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "oklch(0.48 0 0)"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "32px"
  button-ghost-hover:
    backgroundColor: "oklch(0.93 0 0)"
    textColor: "oklch(0.11 0 0)"
    rounded: "{rounded.md}"
  button-outline:
    backgroundColor: "oklch(0.95 0 0)"
    textColor: "oklch(0.11 0 0)"
    borderColor: "oklch(0.88 0 0)"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "32px"
  card-default:
    backgroundColor: "oklch(1 0 0)"
    textColor: "oklch(0.11 0 0)"
    rounded: "{rounded.lg}"
    padding: "16px"
  input-default:
    backgroundColor: "oklch(0.95 0 0)"
    textColor: "oklch(0.11 0 0)"
    rounded: "{rounded.md}"
    height: "32px"
---

# Design System: Zentri

## 1. Overview

**Creative North Star: "iOS Liquid Glass — Pure Monochrome Premium"**

Zentri's interface is a private financial advisor rendered in pure black and white. The design is uncompromising in its restraint: no amber in the chrome, no warm tones in navigation or buttons. The palette is achromatic throughout the UI shell. Color appears only in data-driven elements — BUY/SELL/HOLD signals, gain/loss indicators — where it carries semantic weight. The glass effect creates depth and premium feel without any gradient or decorative color.

The body sits at iOS System Gray 6 (`oklch(0.95 0 0)`) in light mode and true black (`oklch(0 0 0)`) in dark mode. Glass panels (sidebar, nav, cards) float above this base using `backdrop-filter: blur + saturate`, creating the iOS Liquid Glass effect through contrast alone — no gradients, no shadows, no color.

**Key Characteristics:**
- Pure monochrome chrome: all UI shell elements are black, white, and gray only
- iOS Liquid Glass: glass panels use `backdrop-filter` over a gray/black body — depth from contrast, not decoration
- Body has `background-color` only — no `background-image`, no gradient
- Geist Sans for UI labels; Geist Mono exclusively for financial data (prices, quantities, percentages)
- BUY/SELL/HOLD signals always carry label and color — never color alone
- System theme (respects OS preference via `next-themes`); both modes equally considered

## 2. Colors: The Monochrome Palette

Zero chroma in the UI shell. Depth through lightness steps only.

### Light Mode Chrome
- **Body Background** (`oklch(0.95 0 0)`): iOS System Gray 6. Visibly off-white — distinct from pure white cards but not gray enough to feel heavy.
- **Card Surface** (`oklch(1 0 0)`): Pure white. Cards lift above the body by color alone, no shadow needed.
- **Ink Dark** (`oklch(0.11 0 0)`): Near-black primary text. Also the primary button fill in light mode.
- **Quiet Text** (`oklch(0.48 0 0)`): iOS gray secondary text — nav defaults, labels, placeholders.
- **Muted Surface** (`oklch(0.93 0 0)`): Hover fills, secondary surface backgrounds.
- **Border** (`oklch(0.88 0 0)`): Very light gray. Present, not prominent.

### Dark Mode Chrome
- **Body Background** (`oklch(0 0 0)`): True black. Not near-black — `#000000`.
- **Card Surface** (`oklch(0.13 0 0)`): iOS Dark surface (~`#1c1c1e`). Cards lift above true black by lightness alone.
- **Foreground** (`oklch(0.97 0 0)`): Near-white primary text. Also the primary button fill in dark mode.
- **Quiet Text** (`oklch(0.60 0 0)`): iOS dark gray secondary text.
- **Border** (`oklch(1 0 0 / 10%)`): White at 10% — hairline separator.

### Data Accents (Signal-only — never appear in navigation or buttons)
- **Gain / BUY:** Muted green tint. Text `oklch(0.35 0.10 145)`, background `oklch(0.95 0.05 145 / 15%)`.
- **Loss / SELL:** Alert Red `oklch(0.577 0.245 27.325)`. Text, background tint `/ 10%`, border `/ 30%`.
- **Hold / Neutral:** Muted surface fill, quiet-text color. No chroma.
- **Optional amber accent:** `oklch(0.62 0.12 58)` is permitted ONLY for data-driven elements (e.g., AI recommendation badge, signal strength indicator). It must never appear on navigation, buttons, or any chrome element.

### Chart Ramp (achromatic)
Five steps from `oklch(0.87 0 0)` (lightest) to `oklch(0.269 0 0)` (darkest). Fully achromatic — no hue conflicts with signal palette.

### Named Rules
**The Zero-Chroma Chrome Rule.** Navigation, buttons, sidebar, header — all are black, white, or gray. No amber, no blue, no teal appears in any chrome element. Chroma lives in data, not in the UI shell.

**The Signal Rule.** BUY, SELL, and HOLD are never encoded by color alone. Every signal badge carries its text label. Color reinforces; it does not replace.

## 3. iOS Liquid Glass Effect

The glass effect in Zentri is created by the contrast between the body background and translucent glass panels. No gradient is required — the blur and saturation of `backdrop-filter` do the work.

### How It Works
1. Body: solid `background-color` only (gray in light, black in dark). No background-image.
2. Glass surfaces (sidebar, nav): `background: oklch(1 0 0 / 65%)` in light, `oklch(1 0 0 / 7%)` in dark.
3. `backdrop-filter: blur(32px) saturate(180%)` — blurs and brightens content behind the panel.
4. `box-shadow: inset 0 1px 0 var(--glass-specular)` — top highlight simulates a glass edge.

### Glass Tokens
```css
/* Light mode */
--glass-bg: oklch(1 0 0 / 65%);
--glass-blur: 32px;
--glass-saturate: 180%;
--glass-border: oklch(0.11 0 0 / 8%);
--glass-specular: oklch(1 0 0 / 70%);

/* Dark mode */
--glass-bg: oklch(1 0 0 / 7%);
--glass-blur: 32px;
--glass-saturate: 200%;
--glass-border: oklch(1 0 0 / 12%);
--glass-specular: oklch(1 0 0 / 18%);
```

### `.glass-chrome` Utility Class
Apply this class to any surface that should use the glass treatment (sidebar, sticky nav, floating panels):
```css
.glass-chrome {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  box-shadow: inset 0 1px 0 var(--glass-specular);
}
```
Falls back to solid `var(--background)` in browsers that don't support `backdrop-filter`.

### Sidebar Specifics
The sidebar uses glass variables directly: `--sidebar: oklch(1 0 0 / 65%)` (light) / `oklch(1 0 0 / 7%)` (dark). It must always have `position: sticky` or `position: fixed` with a colored body visible behind it for the glass to read correctly.

## 4. Typography

**Body Font:** Geist (with system-ui, sans-serif fallback)
**Mono Font:** Geist Mono (with Consolas, monospace fallback)

The typographic system uses weight contrast and the proportional/monospaced distinction as its primary hierarchy signals. No decorative color in typography.

### Hierarchy
- **Display** (600, clamp(1.75rem, 3vw, 2.5rem), lh 1.1, ls -0.02em): Page titles, major section headers only.
- **Headline** (600, 1.5rem, lh 1.2, ls -0.01em): Card headings, modal titles.
- **Title** (500, 1rem, lh 1.4): Section titles within cards, table column groups.
- **Body** (400, 0.875rem, lh 1.6): All prose. Max line length 65–72ch.
- **Label** (500, 0.75rem, lh 1.4, ls 0.01em): Form labels, table headers, nav items, badge text.
- **Mono/Data** (400, 0.875rem, lh 1.6, Geist Mono): Prices, percentages, tickers, quantities, dates. Always monospaced.

### Named Rules
**The Mono Signal Rule.** Any numeric value requiring precision — price, quantity, percentage, date — is rendered in Geist Mono. The typeface switch from proportional to monospaced is a visual affordance: this is a measurement, not a label.

**The Weight Contrast Rule.** Hierarchy is established by weight and size, never by color alone. A label is 500 weight; a value below it is 400 weight Mono. The contrast is semantic and perceptual simultaneously.

## 5. Elevation

Zentri uses tonal elevation: surfaces differ in lightness, never through shadow.

- **Light mode:** Body `oklch(0.95 0 0)` → Card `oklch(1 0 0)`. The 5-step lightness lift creates visible separation.
- **Dark mode:** Body `oklch(0 0 0)` → Card `oklch(0.13 0 0)`. The card lifts out of true black by 13 lightness points.
- **No box-shadows** for structural elevation. The inset specular highlight on `.glass-chrome` is the only permitted shadow — it simulates a physical glass edge.
- **1px borders** at `var(--border)` or `var(--glass-border)` close the gap where lightness alone isn't sufficient.

### Named Rules
**The Flat-by-Default Rule.** Surfaces are flat at rest. No box-shadow appears unless a surface is genuinely lifted by user interaction. When depth is needed, reach for tonal fill or the 1px border — not shadow.

**The No-Gradient Rule.** The body has `background-color` only. No `background-image`, no `linear-gradient`, no `radial-gradient` on any surface. The glass effect is the sole source of visual depth.

## 6. Theme Transitions

Smooth 250ms transitions on theme switch prevent jarring flashes:
```css
body, .glass-chrome, [data-slot="card"], main {
  transition: background-color 250ms cubic-bezier(0.16, 1, 0.3, 1),
              border-color 200ms cubic-bezier(0.16, 1, 0.3, 1),
              color 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
```
All transitions are disabled under `prefers-reduced-motion: reduce`.

The theme toggle icon uses `@keyframes icon-spin-in` (defined in `globals.css`): rotate from -90deg + scale(0.5) to 0deg + scale(1). Apply via `animation: icon-spin-in 200ms cubic-bezier(0.16, 1, 0.3, 1)` on the icon element when theme changes.

## 7. Components

### Buttons
Monochrome. 32px default height. 0.625rem radius.

- **Primary (light):** Black fill (`oklch(0.11 0 0)`), white text. One per view.
- **Primary (dark):** White fill (`oklch(0.97 0 0)`), near-black text (`oklch(0.09 0 0)`).
- **Hover:** Lightens/darkens 10% lightness from rest state.
- **Focus:** 3px ring at `var(--ring) / 25%` opacity.
- **Ghost:** Transparent, quiet-text color. Hover fills with muted surface, shifts to ink-dark. Default for secondary actions.
- **Outline:** Body background fill, border stroke. Secondary actions needing more presence than ghost.
- **Destructive:** Alert-red tint fill (`/10%`), alert-red text. Genuinely destructive actions only.

### Badges (Financial Signals)
Pill-shaped (9999px radius), 20px height, 8px horizontal padding, 0.75rem label text.

- **BUY:** Muted green tint background, green-dark text, green border at 40% opacity. Label "BUY" always present.
- **HOLD:** Muted surface fill, quiet-text color, border. Neutral.
- **SELL:** Alert-red tint (`/10%`), red-dark text, alert-red border (`/30%`). Label "SELL" always present.
- **Categorical:** Dark fill in light mode, white fill in dark mode. No amber unless it carries a signal meaning.

### Cards
White surfaces on gray/black body.

- **Corner Style:** 0.875rem (14px). Intentionally rounded, not aggressive.
- **Background:** Pure white in light (`oklch(1 0 0)`), dark surface in dark (`oklch(0.13 0 0)`).
- **Border:** 1px `var(--border)` — closes the gap where tonal lift alone is insufficient.
- **Internal Padding:** 16px (default), 12px (sm variant).
- **No box-shadows.** No nested cards.

### Inputs
Stroke-style. Border visible at rest.

- **Style:** Muted surface fill, border stroke (1px), 0.625rem radius, 32px height.
- **Focus:** Border shifts to `var(--ring)`; 3px ring at `var(--ring) / 20%`.
- **Placeholder:** Quiet-text color at reduced opacity.
- **Error:** Border and ring shift to `var(--destructive)`.
- **Disabled:** 50% opacity, cursor not-allowed.

### Navigation (Sidebar)
Glass panel. `position: sticky` or `fixed`. Applies `.glass-chrome` class.

- **Default:** Quiet-text, no background fill on items.
- **Hover:** Muted surface fill (`oklch(1 0 0 / 50%)` in light), ink-dark text.
- **Active:** Black fill, white text (light) / white fill, dark text (dark). Monochrome — no amber.

## 8. Do's and Don'ts

### Do:
- **Do** render all prices, quantities, and percentages in Geist Mono. The font switch is a semantic affordance.
- **Do** pair label and color on every BUY/SELL/HOLD signal. Never color alone.
- **Do** keep the body background as `background-color` only — no gradients, no background-image.
- **Do** apply `.glass-chrome` to any sticky/floating panel so it reads as glass over the body.
- **Do** use tonal elevation (white card on gray body) for depth — not shadow.
- **Do** maintain WCAG AA contrast (4.5:1) on all body and label text. Check quiet-text `oklch(0.48 0 0)` on white cards.
- **Do** give sections room to breathe. Cramped layouts undermine "unhurried precision."

### Don't:
- **Don't** put amber, blue, teal, or any chromatic color on navigation items, buttons, or chrome elements. Monochrome only in the UI shell.
- **Don't** add `background-image` or any gradient to `body`. The glass effect depends on a flat, solid body color.
- **Don't** use gamified color pulses, confetti, or visual urgency signals.
- **Don't** use box-shadows for structural elevation. Tonal fill and 1px borders are sufficient.
- **Don't** nest cards. A card inside a card always indicates a layout problem.
- **Don't** use `background-clip: text` with gradients for any heading or metric value.
- **Don't** introduce chromatic accents in chrome. Alert Red for destructive states and optional signal green/amber for data badges are the complete chromatic set.
- **Don't** use Bloomberg-style density: walls of data, monospaced grids, no whitespace, no hierarchy.
