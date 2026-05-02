---
name: Zentri
description: Privacy-first personal financial OS — clear, composed, counsel over data.
colors:
  warm-canvas: "oklch(0.98 0.008 75)"
  card-surface: "oklch(0.995 0.005 75)"
  ink-dark: "oklch(0.15 0.008 60)"
  advisor-amber: "oklch(0.62 0.12 58)"
  amber-foreground: "oklch(0.99 0.004 75)"
  warm-muted: "oklch(0.95 0.007 75)"
  quiet-text: "oklch(0.53 0.008 65)"
  warm-border: "oklch(0.90 0.007 75)"
  alert-red: "oklch(0.577 0.245 27.325)"
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
    backgroundColor: "{colors.advisor-amber}"
    textColor: "{colors.amber-foreground}"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "32px"
  button-primary-hover:
    backgroundColor: "oklch(0.56 0.11 58)"
    textColor: "{colors.amber-foreground}"
    rounded: "{rounded.md}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.quiet-text}"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "32px"
  button-ghost-hover:
    backgroundColor: "{colors.warm-muted}"
    textColor: "{colors.ink-dark}"
    rounded: "{rounded.md}"
  button-outline:
    backgroundColor: "{colors.warm-canvas}"
    textColor: "{colors.ink-dark}"
    rounded: "{rounded.md}"
    padding: "0 10px"
    height: "32px"
  card-default:
    backgroundColor: "{colors.card-surface}"
    textColor: "{colors.ink-dark}"
    rounded: "{rounded.lg}"
    padding: "16px"
  input-default:
    backgroundColor: "{colors.warm-canvas}"
    textColor: "{colors.ink-dark}"
    rounded: "{rounded.md}"
    height: "32px"
---

# Design System: Zentri

## 1. Overview

**Creative North Star: "The Trusted Advisor"**

Zentri's interface is a private financial advisor, not a trading platform. The design is composed, unhurried, and authoritative — not because it is austere, but because it has already done the work. The palette is warm cream and ink, with a single amber accent drawn from the same family as considered counsel: warm, present, functional. Surfaces do not compete for attention; information hierarchy does the work that decoration refuses to do.

The system rejects urgency as an aesthetic. No gamified color pulses, no live-ticker animations designed to simulate momentum. Zentri synthesizes; it does not dump. The interface distinguishes raw data (numbers, tickers, prices) from interpreted insight (LLM recommendations, portfolio signals) through scale, weight, and spatial placement — never through color or visual noise alone. Geist Mono on every price; Geist Sans on every label. The switch between them is the primary signal that separates measurement from metadata.

Note: the proposed warm-canvas and advisor-amber values in this spec represent the intended direction. The current `globals.css` uses a chromaless shadcn/ui baseline. Run `/impeccable craft` to apply these tokens.

**Key Characteristics:**
- Warm cream canvas, ink-dark typography, one amber accent on active and primary elements only
- Flat tonal elevation: surfaces separated by a 1px ring at 10% foreground opacity, never by shadow
- Geist Sans for UI; Geist Mono exclusively for financial data
- BUY/SELL/HOLD signals always carry label and color — never color alone
- System theme (respects OS preference); both modes are equally considered

## 2. Colors: The Counsel Palette

A warm near-achromatic base with one amber accent. The warmth signals human judgment; the restraint signals precision.

### Primary
- **Advisor Amber** (`oklch(0.62 0.12 58)`): The single accent. Active navigation states, primary buttons, focus rings. Warm but not aggressive — the amber of old paper, not a sports car. Never decorative; only functional. If a second amber element appears on the same screen, one of them is wrong.

### Neutral
- **Warm Canvas** (`oklch(0.98 0.008 75)`): Primary page background. Faintly warm. The distance from `#ffffff` is small but meaningful — it signals a private document, not a SaaS landing page.
- **Card Surface** (`oklch(0.995 0.005 75)`): Cards are marginally lighter and warmer than the canvas. They lift through warmth, not shadow.
- **Ink Dark** (`oklch(0.15 0.008 60)`): Primary text. Warm near-black — ink, not screen black.
- **Quiet Text** (`oklch(0.53 0.008 65)`): Secondary text, labels, placeholder, nav defaults. Legible without demanding attention.
- **Warm Muted** (`oklch(0.95 0.007 75)`): Hover fills, muted surface backgrounds.
- **Warm Border** (`oklch(0.90 0.007 75)`): Input strokes, dividers. Present, not prominent.

### Tertiary
- **Alert Red** (`oklch(0.577 0.245 27.325)`): Destructive actions, negative returns, error states. The only other chromatic hue in the system.

### Data Visualization
Chart ramp is fully achromatic: `oklch(0.87 0 0)` (lightest) to `oklch(0.269 0 0)` (darkest), five steps. This avoids hue conflicts with the gain/loss signal palette and keeps charts calm.

### Named Rules
**The One Voice Rule.** Advisor Amber appears on at most one active element per screen. Its rarity is the point. A screen saturated with amber has no advisor.

**The Signal Rule.** BUY, SELL, and HOLD are never encoded by color alone. Every signal badge carries its text label. Color reinforces; it does not replace. Green does not mean BUY unless the word "BUY" is also present.

## 3. Typography

**Body Font:** Geist (with system-ui, sans-serif fallback)
**Mono Font:** Geist Mono (with Consolas, monospace fallback)

**Character:** A single, highly legible geometric sans with warm optical texture at text sizes. The real typographic story in Zentri is the contrast between Geist Sans (labels, copy, navigation) and Geist Mono (prices, quantities, percentages). That switch is a semantic affordance: this number is a measurement, not prose.

### Hierarchy
- **Display** (600, clamp(1.75rem, 3vw, 2.5rem), lh 1.1, ls -0.02em): Page titles, major section headers only.
- **Headline** (600, 1.5rem, lh 1.2, ls -0.01em): Card headings, modal titles.
- **Title** (500, 1rem, lh 1.4): Section titles within cards, table column groups.
- **Body** (400, 0.875rem, lh 1.6): All prose. Max line length 65–72ch.
- **Label** (500, 0.75rem, lh 1.4, ls 0.01em): Form labels, table headers, nav items, badge text.
- **Mono/Data** (400, 0.875rem, lh 1.6, Geist Mono): Prices, percentages, tickers, quantities, dates. Always monospaced.

### Named Rules
**The Mono Signal Rule.** Any numeric value that requires precision — price, quantity, percentage, date — is rendered in Geist Mono. The typeface switch from proportional to monospaced is a visual affordance: this is a measurement, not a label.

## 4. Elevation

Zentri uses tonal elevation exclusively. There are no box-shadows in the system.

Cards separate from the page via `box-shadow: inset 0 0 0 1px oklch(0.15 0.008 60 / 10%)` — a 1px ring at 10% foreground opacity. This boundary is present but never dominant. The card surface is marginally lighter and warmer than the canvas; the ring closes the remaining visual gap. Together they create legible depth without any artifact that reads as "floating" or "lifted."

The sidebar uses a right border (`border-right: 1px solid {warm-border}`) to separate from the main canvas. No shadow.

### Named Rules
**The Flat-by-Default Rule.** Surfaces are flat at rest. No box-shadow appears unless a surface is genuinely lifted by user interaction. When depth is needed, reach for tonal fill or the 1px foreground ring — not shadow.

## 5. Components

### Buttons
Composed, not theatrical. 32px default height. 0.625rem radius (gently rounded, not pill-shaped at default size).

- **Primary:** Advisor Amber fill, near-white text, 10px horizontal padding. The primary action button. One per view.
- **Hover:** Deepens amber to `oklch(0.56 0.11 58)`. Perceptible; not dramatic.
- **Focus:** 3px ring at amber/25% opacity. Clear.
- **Ghost:** Transparent, quiet-text color. Hover fills with warm-muted, shifts to ink-dark. Default for secondary actions.
- **Outline:** Canvas background, warm-border stroke. Secondary actions needing more presence than ghost.
- **Destructive:** Alert-red tint fill (`/10%`), alert-red text. Genuinely destructive actions only (delete, remove). Never for warnings.

### Badges (Financial Signals)
Pill-shaped (9999px radius), 20px height, 8px horizontal padding, 0.75rem label text.

- **BUY:** Muted green tint background, green-dark text, green border at 40% opacity. Label "BUY" always present.
- **HOLD:** Warm-muted fill, quiet-text color, warm-border. Neutral.
- **SELL:** Alert-red tint (`/10%`), red-dark text, alert-red border (`/30%`). Label "SELL" always present.
- **Default:** Advisor Amber fill, amber-foreground text. For non-financial categorical badges.

### Cards
Flat surfaces with tonal ring boundary.

- **Corner Style:** Noticeably rounded, 0.875rem (14px). Intentional; not aggressively round.
- **Background:** Card Surface (`oklch(0.995 0.005 75)`).
- **Shadow Strategy:** 1px inset ring at foreground/10% only. No box-shadow.
- **Internal Padding:** 16px (default), 12px (sm variant).
- **Footer:** Warm-muted at 50% opacity fill, top border, 16px padding.

No nested cards. Ever.

### Inputs
Stroke-style. The border is visible at rest — not only on focus.

- **Style:** Warm canvas fill, warm-border stroke (1px), 0.625rem radius, 32px height.
- **Focus:** Border shifts to advisor-amber; 3px amber ring at 20% opacity.
- **Placeholder:** Quiet-text color at reduced opacity.
- **Error:** Border and ring shift to alert-red.
- **Disabled:** 50% opacity, cursor not-allowed.

### Navigation (Sidebar)
56px wide panel, `border-right: 1px solid {warm-border}`, no shadow. Nav items are 36px tall, 0.625rem radius, full-width within the sidebar.

- **Default:** Quiet-text, no background fill.
- **Hover:** Warm-muted fill, ink-dark text.
- **Active:** Advisor Amber fill, amber-foreground text, medium weight (500). This is the largest amber surface in the UI — still under 10% of total screen area.

## 6. Do's and Don'ts

### Do:
- **Do** render all prices, quantities, and percentages in Geist Mono. The font switch is a semantic affordance.
- **Do** pair label and color on every BUY/SELL/HOLD signal. Never color alone.
- **Do** keep advisor-amber to one active element per view. Two amber elements means one is wrong.
- **Do** use the 1px inset ring (`ring-1 ring-foreground/10`) for card boundaries instead of shadows.
- **Do** give sections room to breathe. Cramped layouts undermine "unhurried precision."
- **Do** use concise, direct labels. "Remove" not "Click here to remove this item."
- **Do** maintain WCAG AA contrast (4.5:1) on all body and label text. Check quiet-text on all background surfaces.

### Don't:
- **Don't** use gamified color pulses, confetti, or visual urgency signals. Zentri is the opposite of Robinhood.
- **Don't** use purple/teal gradients, glass cards, floating hero sections, or generic startup template aesthetics.
- **Don't** use Bloomberg-style density: walls of data, monospaced grids, no whitespace, no hierarchy.
- **Don't** use dark neon, glowing outlines, or matrix-adjacent visuals.
- **Don't** use `border-left` greater than 1px as a colored accent stripe on cards, alerts, or list items.
- **Don't** use `background-clip: text` with gradients for any heading or metric value.
- **Don't** nest cards. A card inside a card always indicates a layout problem, not a design solution.
- **Don't** use box-shadows. Tonal fill and the foreground ring are sufficient.
- **Don't** introduce a second chromatic accent. Alert Red and Advisor Amber are the complete chromatic set.
