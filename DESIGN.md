---
name: Zentri
description: Privacy-first personal financial OS — iOS Liquid Glass premium, floating card aesthetic.
colors:
  # Chrome palette (light) — iOS blue-gray tinted
  body-bg: "oklch(0.955 0.006 264)"
  card-surface: "oklch(1 0 0)"
  ink-dark: "oklch(0.11 0 0)"
  quiet-text: "oklch(0.48 0 0)"
  muted-surface: "oklch(0.925 0.004 264)"
  border: "oklch(0.88 0 0)"
  # Chrome palette (dark) — true black iOS
  dark-body-bg: "oklch(0 0 0)"
  dark-card-surface: "oklch(0.13 0 0)"
  dark-foreground: "oklch(0.97 0 0)"
  dark-quiet-text: "oklch(0.60 0 0)"
  dark-border: "oklch(1 0 0 / 10%)"
  # Data-driven accents (signals only — never chrome)
  signal-green-bg: "oklch(0.95 0.05 145 / 12%)"
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
  light-bg: "oklch(1 0 0 / 68%)"
  light-blur: "32px"
  light-saturate: "200%"
  light-border: "oklch(0.11 0 0 / 8%)"
  light-specular: "oklch(1 0 0 / 72%)"
  # Dark mode
  dark-bg: "oklch(1 0 0 / 7%)"
  dark-blur: "32px"
  dark-saturate: "200%"
  dark-border: "oklch(1 0 0 / 10%)"
  dark-specular: "oklch(1 0 0 / 18%)"
shadows:
  # Ambient float shadow — cards hover above the background
  card-light: "0 1px 4px oklch(0 0 0 / 5%), 0 6px 20px oklch(0 0 0 / 5%)"
  card-dark: "0 1px 0 oklch(1 0 0 / 5%), 0 4px 24px oklch(0 0 0 / 55%)"
  # Elevated overlays (modals, popovers)
  overlay-light: "0 8px 40px oklch(0 0 0 / 16%), 0 0 0 1px oklch(0 0 0 / 6%)"
  overlay-dark: "0 8px 40px oklch(0 0 0 / 70%), 0 0 0 1px oklch(1 0 0 / 8%)"
rounded:
  xs: "0.375rem"
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
  xl: "1.25rem"
  2xl: "1.5rem"
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
    padding: "0 12px"
    height: "34px"
  button-primary-dark:
    backgroundColor: "oklch(0.97 0 0)"
    textColor: "oklch(0.09 0 0)"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "34px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "oklch(0.48 0 0)"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "34px"
  button-ghost-hover:
    backgroundColor: "oklch(0 0 0 / 5%)"
    textColor: "oklch(0.11 0 0)"
    rounded: "{rounded.md}"
  card-default:
    backgroundColor: "oklch(1 0 0)"
    textColor: "oklch(0.11 0 0)"
    rounded: "{rounded.xl}"
    padding: "20px"
    shadow: "{shadows.card-light}"
  input-default:
    backgroundColor: "oklch(0.95 0 0)"
    textColor: "oklch(0.11 0 0)"
    rounded: "{rounded.md}"
    height: "34px"
---

# Design System: Zentri

## 1. Overview

**Creative North Star: "iOS Liquid Glass — Floating Premium"**

Zentri's interface is a private financial advisor rendered in precise monochrome. The chrome (sidebar, nav, overlays) uses iOS Liquid Glass — translucent frosted panels floating above the background. Content cards are solid white surfaces that float via soft ambient shadows, like cards resting on a table. The combination of glass chrome + floating solid cards is what makes this feel iOS-native rather than generic web.

The body sits at iOS System Gray 6 — a very slightly blue-tinted gray (`oklch(0.955 0.006 264)`) — in light mode. This subtle tint is essential: it gives the glass effect something chromatic to blur, and it makes pure white cards read as genuinely floating. In dark mode the body is true black (`oklch(0 0 0)`).

**Key Characteristics:**
- iOS blue-gray body (not pure neutral gray) — `#F2F2F7` equivalent
- Glass chrome (sidebar, nav) + floating solid cards — two distinct layers
- Ambient card shadow: `0 1px 4px oklch(0 0 0 / 5%), 0 6px 20px oklch(0 0 0 / 5%)` — cards hover above the background
- 20px corner radius on main content cards — generous, iOS-native
- Zero chroma in UI shell elements (nav, buttons, sidebar) — color only in financial signals
- Geist Sans for UI; Geist Mono exclusively for financial data (prices, quantities, percentages)
- BUY/SELL/HOLD always carry label and color — never color alone
- Both light and dark modes equally considered

## 2. Colors

### Light Mode

The body is iOS `systemGray6` — a subtly blue-tinted off-white. Not pure gray. This tint is what gives the glass effect depth and makes white cards read as floating.

- **Body Background** (`oklch(0.955 0.006 264)`): iOS System Gray 6. The slight blue cast (~`#F2F2F7`) is intentional — it's the iOS light mode foundation.
- **Card Surface** (`oklch(1 0 0)`): Pure white. Elevated above the body by both tonal contrast and ambient shadow.
- **Ink Dark** (`oklch(0.11 0 0)`): Near-black primary text. Primary button fill in light mode.
- **Quiet Text** (`oklch(0.48 0 0)`): Secondary text — nav items, labels, placeholders.
- **Muted Surface** (`oklch(0.925 0.004 264)`): Hover fills, table row stripes. Slightly darker and slightly blue-tinted.
- **Border** (`oklch(0.88 0 0)`): Hairline dividers. On white cards these read as very subtle separators.

### Dark Mode

True black foundation. Cards lift out of black via tonal contrast. Shadows are deeper and more dramatic on black.

- **Body Background** (`oklch(0 0 0)`): True black. `#000000`, not near-black.
- **Card Surface** (`oklch(0.13 0 0)`): iOS Dark elevated surface. Lifts from black by 13 lightness points — clearly visible separation.
- **Foreground** (`oklch(0.97 0 0)`): Near-white primary text. Also the primary button fill in dark mode.
- **Quiet Text** (`oklch(0.60 0 0)`): Secondary text in dark mode.
- **Border** (`oklch(1 0 0 / 10%)`): White at 10% opacity — hairline.

### Data Accents (Signal-only)

These colors appear exclusively on financial data elements. Never on navigation, buttons, or any structural chrome.

- **Gain / BUY:** Text `oklch(0.35 0.10 145)`, background `oklch(0.95 0.05 145 / 12%)`.
- **Loss / SELL:** Alert Red `oklch(0.577 0.245 27.325)`, background tint `/ 8%`.
- **Hold / Neutral:** Muted surface fill, quiet-text color. No chroma.
- **Amber:** `oklch(0.62 0.12 58)` — only for data signals (AI badge, strength indicator). Never in chrome.

### Chart Ramp (achromatic)

Five steps from light to dark: `oklch(0.87 0 0)` → `oklch(0.72 0 0)` → `oklch(0.556 0 0)` → `oklch(0.439 0 0)` → `oklch(0.269 0 0)`.

### Named Rules

**The Zero-Chroma Chrome Rule.** Navigation, buttons, sidebar, header — monochrome only. No blue, amber, teal, or any hue in the UI shell. The body's subtle blue tint is the only permitted chroma in chrome, and it is never used decoratively on individual elements.

**The Signal Rule.** BUY, SELL, and HOLD are never encoded by color alone. Every signal badge carries its text label. Color reinforces; it does not replace.

## 3. iOS Liquid Glass Effect

### How It Works

Two distinct surface types work together:

1. **Glass Chrome** (sidebar, nav, floating overlays): Translucent, blurs the body behind it.
   - Body behind the glass has the iOS blue-gray tint — this is what gets blurred into the frosted look.
   - `background: oklch(1 0 0 / 68%)` light / `oklch(1 0 0 / 7%)` dark.
   - `backdrop-filter: blur(32px) saturate(200%)`.
   - `box-shadow: inset 0 1px 0 var(--glass-specular)` — top highlight simulates glass edge.

2. **Floating Solid Cards** (content, KPI, charts): Opaque white/dark surfaces that sit above the body via shadow.
   - `background: var(--card)` — fully opaque.
   - `box-shadow: var(--card-shadow)` — soft ambient float.
   - No `backdrop-filter`. Cards do not blur the background.

The glass chrome blurs the background; the solid cards hover above it with shadow. Both layers together create the "floating elements on frosted base" iOS feel.

### Glass Tokens

```css
/* Light mode */
--glass-bg: oklch(1 0 0 / 68%);
--glass-blur: 32px;
--glass-saturate: 200%;
--glass-border: oklch(0.11 0 0 / 8%);
--glass-specular: oklch(1 0 0 / 72%);

/* Dark mode */
--glass-bg: oklch(1 0 0 / 7%);
--glass-blur: 32px;
--glass-saturate: 200%;
--glass-border: oklch(1 0 0 / 10%);
--glass-specular: oklch(1 0 0 / 18%);
```

### Card Shadow Tokens

```css
/* Light mode — soft ambient float */
--card-shadow: 0 1px 4px oklch(0 0 0 / 5%), 0 6px 20px oklch(0 0 0 / 5%);

/* Dark mode — deeper float on true black */
--card-shadow: 0 1px 0 oklch(1 0 0 / 5%), 0 4px 24px oklch(0 0 0 / 55%);
```

### `.glass-chrome` Utility Class

```css
.glass-chrome {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  box-shadow: inset 0 1px 0 var(--glass-specular);
}
```

Falls back to solid `var(--background)` in browsers that don't support `backdrop-filter`.

## 4. Typography

**Body Font:** Geist (system-ui, sans-serif fallback)
**Mono Font:** Geist Mono (Consolas, monospace fallback)

### Hierarchy

- **Display** (600, clamp(1.75rem, 3vw, 2.5rem), lh 1.1, ls -0.02em): Page titles only.
- **Headline** (600, 1.5rem, lh 1.2, ls -0.01em): Card headings, modal titles.
- **Title** (500, 1rem, lh 1.4): Section headers within cards.
- **Body** (400, 0.875rem, lh 1.6): All prose. Max 65–72ch line length.
- **Label** (500, 0.75rem, lh 1.4, ls 0.01em): Form labels, table headers, nav items, badge text.
- **Mono/Data** (400, 0.875rem, lh 1.6, Geist Mono): Every price, quantity, percentage, date.

### Named Rules

**The Mono Signal Rule.** Numeric values requiring precision are rendered in Geist Mono. The typeface shift from proportional to monospaced is a semantic affordance: "this is a measurement, not a label."

**The Weight Contrast Rule.** Hierarchy via weight and size, never color alone. A label is 500 weight; its value below is 400 Mono. Contrast is semantic and perceptual simultaneously.

## 5. Elevation

Two mechanisms work together — tonal lift (color contrast) and ambient shadow (float effect).

### Tonal Lift

- **Light mode:** Body `oklch(0.955 0.006 264)` → Card `oklch(1 0 0)`. ~4.5 lightness steps + blue-gray to pure white creates clear separation.
- **Dark mode:** Body `oklch(0 0 0)` → Card `oklch(0.13 0 0)`. Cards lift 13 lightness points out of true black.

### Ambient Shadow (Cards)

Solid content cards use a soft ambient shadow to float above the body. This is not structural elevation via shadow — it is the primary "floating card" aesthetic that makes the interface feel iOS-native.

```css
/* Light */
--card-shadow: 0 1px 4px oklch(0 0 0 / 5%), 0 6px 20px oklch(0 0 0 / 5%);
/* Dark */
--card-shadow: 0 1px 0 oklch(1 0 0 / 5%), 0 4px 24px oklch(0 0 0 / 55%);
```

Apply `box-shadow: var(--card-shadow)` to all main content cards. Do not increase shadow size — the values above are calibrated. On dark mode, the deeper shadow makes the card read distinctly from the true black body.

### What Gets Shadow vs. What Gets Glass

| Surface | Treatment |
|---|---|
| Sidebar, top nav | `.glass-chrome` — translucent + `backdrop-filter` |
| Bottom tab bar | `.glass-chrome` — translucent + `backdrop-filter` |
| Content cards, KPI panels, chart containers | `box-shadow: var(--card-shadow)` — solid + float |
| Modals, command palette | `.glass-chrome` OR solid with `--overlay-shadow` |
| Dropdowns, tooltips | Solid + `--overlay-shadow` |

### Named Rules

**The Two-Layer Rule.** Glass chrome blurs the background layer. Solid cards float above it with shadow. Never mix these: a content card should not have `backdrop-filter`, and a sidebar panel should not have a drop shadow.

**The No-Gradient Rule.** The body has `background-color` only. No `background-image`, no `linear-gradient`, no `radial-gradient` on any surface. The iOS blue-gray tint in the body color is a single color value, not a gradient.

**The Ambient-Only Shadow Rule.** The `--card-shadow` values are fixed — do not make them larger or add colored shadows to cards. Use the specular highlight (`inset 0 1px 0 var(--glass-specular)`) only on glass surfaces.

## 6. Corner Radius

The radius scale uses 20px as the default for content cards — matching iOS app card rounding. This is more generous than generic web cards.

- **Inputs, small buttons:** `rounded-md` (0.75rem / 12px)
- **Badges, pills:** `rounded-full` (9999px)
- **Nav items, icon buttons:** `rounded-[10px]` or `rounded-lg` (1rem / 16px)
- **Content cards, KPI panels:** `rounded-2xl` (1.5rem / 24px) — the standard card radius
- **Chart containers, large sections:** `rounded-2xl` (1.5rem / 24px)
- **Modals, command palette:** `rounded-2xl` (1.5rem / 24px)

## 7. Theme Transitions

```css
body, .glass-chrome, [data-slot="card"], main {
  transition: background-color 250ms cubic-bezier(0.16, 1, 0.3, 1),
              border-color 200ms cubic-bezier(0.16, 1, 0.3, 1),
              color 200ms cubic-bezier(0.16, 1, 0.3, 1),
              box-shadow 250ms cubic-bezier(0.16, 1, 0.3, 1);
}
```

All transitions disabled under `prefers-reduced-motion: reduce`.

Theme toggle uses `@keyframes icon-spin-in`: rotate from -90deg + scale(0.5) to 0deg + scale(1), 200ms ease-out-quart.

## 8. Components

### Buttons

Monochrome. 34px default height. 0.75rem radius.

- **Primary (light):** Black fill (`oklch(0.11 0 0)`), white text. One per view.
- **Primary (dark):** White fill (`oklch(0.97 0 0)`), near-black text.
- **Ghost:** Transparent, quiet-text color. Hover: `oklch(0 0 0 / 5%)` fill, ink-dark text.
- **Outline:** Body fill, 1px border. For secondary actions needing more weight than ghost.
- **Destructive:** Alert-red tint (`/10%`) fill, alert-red text.

### Badges (Financial Signals)

Pill-shaped (9999px), 20px height, 8px horizontal padding.

- **Gain / BUY:** `var(--signal-gain-bg)` fill, `var(--signal-gain-text)` color. Label always visible.
- **Hold / Neutral:** Muted surface fill, quiet-text.
- **Loss / SELL:** `var(--signal-loss-bg)` fill, `var(--destructive)` color. Label always visible.
- **Categorical:** Dark fill (light mode) / white fill (dark mode). No chroma unless semantic.

### Cards

Pure white (light) or dark surface (dark), floating on the body.

- **Corner radius:** `rounded-2xl` (1.5rem / 24px)
- **Background:** `var(--card)` — fully opaque
- **Border:** 1px `var(--border)`
- **Shadow:** `var(--card-shadow)` — soft ambient float
- **Internal padding:** 20px default, 16px compact variant
- **No nested cards.** A card inside a card is always a layout problem.

### Inputs

Stroke-style. 34px height. 0.75rem radius.

- **Style:** Muted surface fill, 1px border stroke.
- **Focus:** Border → `var(--ring)`, 3px ring at `var(--ring) / 20%`.
- **Error:** Border and ring → `var(--destructive)`.
- **Disabled:** 50% opacity, cursor not-allowed.

### Navigation (Sidebar)

Glass panel. `position: sticky` or `fixed`. Uses `.glass-chrome`.

- **Default nav items:** Quiet-text, no fill.
- **Hover:** `oklch(1 0 0 / 50%)` fill (light) / `oklch(1 0 0 / 8%)` (dark), ink-dark text.
- **Active:** Black fill, white text (light) / white fill, dark text (dark).
- **Section labels:** 10px, 500 weight, tracking 0.08em, uppercase. Quiet-text at 50% opacity.

## 9. Do's and Don'ts

### Do:
- **Do** render all prices, quantities, and percentages in Geist Mono.
- **Do** pair label and color on every BUY/SELL/HOLD signal — never color alone.
- **Do** keep body background as `background-color` only — the iOS blue-gray tint is a single solid color, not a gradient.
- **Do** apply `.glass-chrome` to sidebar, top nav, bottom tab bar, and floating overlays.
- **Do** apply `box-shadow: var(--card-shadow)` to all content cards and KPI panels.
- **Do** use `rounded-2xl` (24px) on main content cards — generous radius is essential to the iOS feel.
- **Do** maintain WCAG AA contrast (4.5:1) on all text. Check quiet-text `oklch(0.48 0 0)` on white cards.
- **Do** give content room to breathe — 20px card padding minimum, 24px gap between cards.

### Don't:
- **Don't** put any chromatic color (blue, amber, teal, green) on nav items, buttons, or chrome elements.
- **Don't** add `background-image` or any gradient to `body` or any card surface.
- **Don't** use `backdrop-filter` on content cards — glass is only for chrome.
- **Don't** increase card shadow beyond the calibrated `--card-shadow` values.
- **Don't** use side-stripe borders (`border-l-2`, `border-r-2` as colored accents) on any card or list item.
- **Don't** use `background-clip: text` with gradients — no gradient text of any kind.
- **Don't** nest cards.
- **Don't** use gamified color pulses, confetti, or visual urgency signals.
- **Don't** use Bloomberg-style data density — synthesize, don't dump.
