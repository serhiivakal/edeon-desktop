# Edeon Design Tokens System

This document outlines Edeon's central design tokens for color, spacing, typography, and theme overrides. These tokens are mapped in `src/styles/tokens.css` and are dynamically updated by Edeon's theme provider.

---

## 1. Spacing & Density Scale
Edeon uses a 4px grid spacing system:
*   `--space-1`: 4px
*   `--space-2`: 8px
*   `--space-3`: 12px
*   `--space-4`: 16px
*   `--space-5`: 20px
*   `--space-6`: 24px
*   `--space-8`: 32px

Density configurations scale the margins and component paddings dynamically:
*   **Compact**: row heights are scaled down to 28px, using a 0.75x spacing multiplier.
*   **Default**: Standard desktop scaling.
*   **Comfortable**: Row heights at 44px, using a 1.25x spacing multiplier.

---

## 2. Color System & Semantic Meanings

To ensure consistent representation across model tiers, applicability domains, and risk parameters, we use the following semantic groups:

| Status Class | Value (Light Mode) | Value (Dark Mode) | Intended Use |
|---|---|---|---|
| **Good** | `#16a34a` / `#f0fdf4` | `#4ade80` / `rgba(74, 222, 128, 0.1)` | AD In-domain, approved compounds, low toxicity |
| **Moderate** | `#ca8a04` / `#fefce8` | `#facc15` / `rgba(250, 204, 21, 0.1)` | AD Borderline, restricted, warning |
| **Poor** | `#dc2626` / `#fef2f2` | `#f87171` / `rgba(248, 113, 113, 0.1)` | AD Out-of-domain, banned, high toxicity |
| **Unknown** | `#71717a` / `#f4f4f5` | `#a1a1aa` / `rgba(161, 161, 170, 0.1)` | Missing calculations, pending |

### Tier Badges
*   `--color-tier-1`: `#2563eb` (Light) / `#60a5fa` (Dark)
*   `--color-tier-2`: `#6366f1` (Light) / `#818cf8` (Dark)
*   `--color-tier-3`: `#8b5cf6` (Light) / `#a78bfa` (Dark)
*   `--color-tier-4`: `#a855f7` (Light) / `#c084fc` (Dark)

---

## 3. Core Theme Variables

The following system tokens control backgrounds, borders, and text contrast:

```css
/* Light mode defaults */
--color-surface-base: #ffffff;
--color-surface-raised: #fafafa;
--color-surface-overlay: #ffffff;
--color-border-subtle: #e4e4e7;
--color-border-default: #d4d4d8;
--color-border-strong: #71717a;

--color-text-primary: #18181b;
--color-text-secondary: #52525b;
--color-text-tertiary: #71717a;

--color-action-primary: #2563eb;
--color-action-primary-hover: #1d4ed8;

/* Dark mode overrides */
--color-surface-base: #09090b;
--color-surface-raised: #18181b;
--color-surface-overlay: #27272a;
--color-border-subtle: #27272a;
--color-border-default: #3f3f46;
--color-border-strong: #71717a;

--color-text-primary: #fafafa;
--color-text-secondary: #d4d4d8;
--color-text-tertiary: #a1a1aa;
```
