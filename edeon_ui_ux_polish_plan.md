# Edeon UI/UX Polish — Implementation Plan for Coding Agent

**Audience:** coding agent.
**Goal:** convert Edeon from "technically excellent product" into "technically excellent product that feels professional within 60 seconds of first launch." Focus on the polish layer that drives commercial impressions: first-launch experience, trust signals, workflow lubrication, and visual consistency.

**Scope:** purely frontend / UX work. No new ML models. No new scientific capabilities. No backend service changes beyond what's needed to support new UI surfaces.

**Time estimate:** 6–9 weeks total across all three priority tiers. Can stop at the end of any tier if time runs out.

---

## 0. Context and Hard Rules

**Hard rule 1: no new scientific features in this plan.**
The product is technically complete (90-day plan A–F passing). This work is about presentation, discoverability, and polish — not capability additions. If during implementation the agent identifies a scientific gap, document it for a future plan and continue with UX work.

**Hard rule 2: consistency beats novelty.**
Where the codebase already has patterns (button styles, color tokens, spacing units), use them. Where patterns conflict, prefer the most-used pattern in the codebase and standardize the rest to match. Introducing a new visual language for a single polish feature is forbidden.

**Hard rule 3: no regressions in existing functionality.**
Every change must preserve existing behavior. Every PR must include verification that existing tests still pass. Visual changes are acceptable; behavioral changes to existing features are not in scope.

**Hard rule 4: keyboard accessibility from day one.**
Every new component must be keyboard navigable, support Tab/Shift+Tab focus traversal, and use appropriate ARIA attributes. This is not a future enhancement — it's a baseline.

**Hard rule 5: dark mode parity from day one.**
Every new component must work in both light and dark modes from initial implementation. Don't ship a light-only component and "add dark mode later" — that produces visual inconsistency that's hard to fix retroactively.

---

## 1. Tech Stack Assumptions

Building on the existing Edeon stack:

- **React 18+** with TypeScript strict mode (per the recent validation report, `npx tsc --noEmit` passes cleanly)
- **Zustand** for state stores (existing convention)
- **Tauri** IPC for backend communication
- **CSS Modules** or **Tailwind** (use whatever the existing codebase uses; the agent must check first)

**New libraries to introduce:**

- **`cmdk` ≥ 1.0** (Vercel's command palette primitive) — for Group B (Command Palette). MIT licensed, ~7KB, accessible, widely used. Alternative: `kbar` if `cmdk` integration is problematic.
- **`driver.js` ≥ 1.3** for Group A (Onboarding Tour). MIT licensed, ~10KB, no React-specific dependencies. Alternative: `react-joyride` if a React-native approach is preferred (heavier but more idiomatic).
- **`react-hotkeys-hook` ≥ 4.5** for Group G (Keyboard Shortcuts). MIT licensed, ~3KB. Existing app may already use it — check first.
- **`lucide-react`** for icons if not already in use (consistent icon system).

No other new dependencies unless individual tasks specifically require them.

---

## 2. Architectural Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Tauri Window                                   │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Top Header Bar (NEW — Group D)                                 │ │
│  │ [Logo] [Project ▾] [Compound ▾] [Search] ... [Settings ▾]      │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                                                                 │ │
│  │  Main Content Area (existing views)                            │ │
│  │  - Honeycomb / Inspector                                       │ │
│  │  - QSAR Studio                                                 │ │
│  │  - Docking Workbench                                           │ │
│  │  - Generation Workbench                                        │ │
│  │  - Knowledge Hub                                               │ │
│  │  - Reports                                                     │ │
│  │  - Workflow Gallery                                            │ │
│  │                                                                 │ │
│  │  Enhanced with:                                                │ │
│  │  - Empty states (Group F)                                      │ │
│  │  - Contextual help icons (Group F)                             │ │
│  │  - Verification badges (Group E)                               │ │
│  │  - Reproducibility info popovers (Group E)                     │ │
│  │  - Citation export buttons (Group C)                           │ │
│  │                                                                 │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Status Bar (NEW — Group D)                                     │ │
│  │ [T1: 13✓] [OPERA: ✓] [API: ✓] [CPU: 23%] | Tasks: 2 running   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─ OVERLAYS ─────────────────────────────────────────────────────┐ │
│  │ - Command Palette (Cmd+K — Group B)                            │ │
│  │ - Keyboard Shortcuts Help (?  — Group G)                       │ │
│  │ - Onboarding Tour (first-launch — Group A)                     │ │
│  │ - Help/About Modal (Group C)                                   │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Repository Layout

```
edeon/
├── src/                                          # React frontend
│   ├── shell/                                    # NEW — global shell components
│   │   ├── TopHeaderBar.tsx
│   │   ├── StatusBar.tsx
│   │   ├── CommandPalette.tsx
│   │   ├── KeyboardShortcutsOverlay.tsx
│   │   ├── OnboardingTour.tsx
│   │   ├── AboutModal.tsx
│   │   └── ThemeProvider.tsx
│   ├── components/
│   │   ├── shared/
│   │   │   ├── EmptyState.tsx                    # NEW
│   │   │   ├── ContextualHelp.tsx                # NEW (the "?" popovers)
│   │   │   ├── VerificationBadge.tsx             # NEW
│   │   │   ├── ReproducibilityInfo.tsx           # NEW
│   │   │   ├── CitationExportButton.tsx          # NEW
│   │   │   ├── ProgressIndicator.tsx             # NEW (standardized)
│   │   │   └── TierBadge.tsx                     # Existing (Phase 0)
│   │   └── ... (existing components)
│   ├── store/
│   │   ├── shellStore.ts                         # NEW — header, status, overlays
│   │   ├── themeStore.ts                         # NEW — dark mode, density
│   │   ├── tourStore.ts                          # NEW — onboarding tour state
│   │   ├── shortcutsRegistry.ts                  # NEW — command/shortcut registry
│   │   └── ... (existing stores)
│   ├── styles/
│   │   ├── tokens.css                            # NEW — design tokens (colors, spacing)
│   │   ├── themes/
│   │   │   ├── light.css
│   │   │   └── dark.css
│   │   └── density/
│   │       ├── compact.css
│   │       ├── default.css
│   │       └── comfortable.css
│   ├── content/
│   │   ├── onboarding/
│   │   │   ├── tour_steps.ts                     # Tour script
│   │   │   └── tour_assets/                      # Reference compound SMILES, etc.
│   │   ├── help/
│   │   │   ├── help_content.json                 # Contextual help texts
│   │   │   └── shortcuts.json                    # Keyboard shortcuts registry
│   │   └── citations/
│   │       └── citation_templates.ts             # Template for BibTeX/RIS/plain
│   └── hooks/
│       ├── useKeyboardShortcut.ts                # Wrapper around react-hotkeys-hook
│       ├── useFirstLaunch.ts                     # Detects first launch via SQLite
│       └── useTheme.ts                           # Theme state hook
├── python/
│   └── edeon_app_meta/                           # NEW (small backend service)
│       ├── __init__.py
│       ├── system_status.py                      # System health for status bar
│       ├── citation_generator.py                 # BibTeX/RIS generation
│       └── first_launch.py                       # First-launch detection
├── docs/
│   ├── UI_UX_POLISH_PLAN.md                      # This document
│   ├── DESIGN_TOKENS.md                          # NEW — design system reference
│   ├── KEYBOARD_SHORTCUTS.md                     # NEW — user-facing
│   ├── ONBOARDING_TOUR_SCRIPT.md                 # NEW — tour script reference
│   ├── CITATION_FORMATS.md                       # NEW — citation reference
│   └── UI_UX_POLISH_NOTES.md                     # Agent deviation log
└── .github/
    └── workflows/
        └── ui_ux_lint.yml                        # Visual regression / a11y checks
```

---

## 4. Design System Foundation (CROSS-CUTTING)

Before any priority tier begins, establish the design token foundation. This is **mandatory and blocks all other work.**

### 4.1 Design tokens

**File:** `src/styles/tokens.css`

```css
:root {
  /* Spacing scale (4px base) */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  /* Typography */
  --font-family-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-family-mono: "JetBrains Mono", "SF Mono", Menlo, monospace;
  --font-size-xs: 11px;
  --font-size-sm: 13px;
  --font-size-base: 14px;
  --font-size-md: 16px;
  --font-size-lg: 18px;
  --font-size-xl: 24px;
  --font-size-2xl: 32px;

  /* Color semantics — applied across the app */
  /* Status: applies to AD status, regulatory status, risk levels uniformly */
  --color-status-good: #16a34a;       /* In-domain, approved, stable, safe */
  --color-status-good-bg: #f0fdf4;
  --color-status-moderate: #ca8a04;   /* Borderline, restricted, moderate */
  --color-status-moderate-bg: #fefce8;
  --color-status-poor: #dc2626;       /* Out-of-domain, banned, susceptible, unsafe */
  --color-status-poor-bg: #fef2f2;
  --color-status-unknown: #71717a;
  --color-status-unknown-bg: #f4f4f5;

  /* Tier colors (Phase 0) */
  --color-tier-1: #2563eb;
  --color-tier-2: #6366f1;
  --color-tier-3: #8b5cf6;
  --color-tier-4: #a855f7;

  /* Surface and chrome */
  --color-surface-base: #ffffff;
  --color-surface-raised: #fafafa;
  --color-surface-overlay: #ffffff;
  --color-border-subtle: #e4e4e7;
  --color-border-default: #d4d4d8;
  --color-border-strong: #71717a;

  /* Text */
  --color-text-primary: #18181b;
  --color-text-secondary: #52525b;
  --color-text-tertiary: #71717a;
  --color-text-inverse: #ffffff;

  /* Interactive */
  --color-action-primary: #2563eb;
  --color-action-primary-hover: #1d4ed8;
  --color-action-primary-active: #1e40af;
  --color-action-secondary: #f4f4f5;
  --color-action-secondary-hover: #e4e4e7;

  /* Shadow */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.05), 0 1px 3px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1), 0 4px 6px rgba(0, 0, 0, 0.05);
  --shadow-overlay: 0 25px 50px rgba(0, 0, 0, 0.25);

  /* Border radius */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  --radius-full: 9999px;

  /* Z-index scale */
  --z-base: 1;
  --z-dropdown: 10;
  --z-sticky: 20;
  --z-overlay: 30;
  --z-modal: 40;
  --z-toast: 50;
}
```

**File:** `src/styles/themes/dark.css`

```css
[data-theme="dark"] {
  --color-status-good: #4ade80;
  --color-status-good-bg: rgba(74, 222, 128, 0.1);
  --color-status-moderate: #facc15;
  --color-status-moderate-bg: rgba(250, 204, 21, 0.1);
  --color-status-poor: #f87171;
  --color-status-poor-bg: rgba(248, 113, 113, 0.1);
  --color-status-unknown: #a1a1aa;
  --color-status-unknown-bg: rgba(161, 161, 170, 0.1);

  --color-tier-1: #60a5fa;
  --color-tier-2: #818cf8;
  --color-tier-3: #a78bfa;
  --color-tier-4: #c084fc;

  --color-surface-base: #09090b;
  --color-surface-raised: #18181b;
  --color-surface-overlay: #27272a;
  --color-border-subtle: #27272a;
  --color-border-default: #3f3f46;
  --color-border-strong: #71717a;

  --color-text-primary: #fafafa;
  --color-text-secondary: #d4d4d8;
  --color-text-tertiary: #a1a1aa;
  --color-text-inverse: #18181b;

  --color-action-primary: #3b82f6;
  --color-action-primary-hover: #60a5fa;
  --color-action-primary-active: #2563eb;
  --color-action-secondary: #27272a;
  --color-action-secondary-hover: #3f3f46;
}
```

### 4.2 Pre-implementation audit

**Mandatory before any task starts.** The agent must:

1. Inventory all existing color usage in the codebase. Identify the dominant color values used today for: status indicators, tier badges, buttons, backgrounds.
2. Compare against the tokens above. Where existing values differ, decide: migrate existing to new tokens, OR adjust tokens to match existing dominant values.
3. Document decisions in `docs/DESIGN_TOKENS.md` with a migration plan.
4. Get the migration plan reviewed before broad token rollout.

This audit prevents weeks of refactoring later. Budget 2 days.

---

## 5. Priority P0 — Critical Polish (2–3 weeks)

These five features deliver the biggest first-impression and trust-signal lift. If implementation time is tight, ship at least P0.

### Group A — Onboarding Tour (5–7 days)

**Goal:** first-launch users see a guided 5-step tour that loads imidacloprid, walks through honeycomb → fate gauge → toxicity panel → CReM workbench → Knowledge Hub, with brief tooltips.

#### Task A1: First-launch detection
**File:** `python/edeon_app_meta/first_launch.py` + `src/hooks/useFirstLaunch.ts`

Backend stores a `first_launch_completed_at` timestamp in SQLite settings table. IPC command `app_meta_get_first_launch_state()` returns `{has_completed: bool, completed_at: str|null}`.

Frontend hook:
```typescript
export function useFirstLaunch() {
  const [isFirstLaunch, setIsFirstLaunch] = useState<boolean>(false);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    invoke<{ has_completed: boolean }>('app_meta_get_first_launch_state')
      .then(state => setIsFirstLaunch(!state.has_completed))
      .finally(() => setLoading(false));
  }, []);
  
  const markCompleted = useCallback(async () => {
    await invoke('app_meta_mark_first_launch_complete');
    setIsFirstLaunch(false);
  }, []);
  
  return { isFirstLaunch, loading, markCompleted };
}
```

**Acceptance:** Fresh app launch shows `isFirstLaunch === true`; after `markCompleted()` called, subsequent launches show `false`.

---

#### Task A2: Tour engine integration
**File:** `src/shell/OnboardingTour.tsx`

Use `driver.js` library. Wrap as React component that:
- Reads tour steps from `src/content/onboarding/tour_steps.ts`
- Renders only when `isFirstLaunch === true` OR user manually triggers via Help menu
- On completion, calls `markCompleted()`
- Provides "Skip Tour" at every step
- Persists "do not show again" preference

**Acceptance:** Tour overlay renders correctly on first launch; "Skip" closes tour and marks complete; tour can be re-triggered from Help menu.

---

#### Task A3: Tour script (5 steps)
**File:** `src/content/onboarding/tour_steps.ts`

```typescript
export const TOUR_STEPS = [
  {
    id: 'welcome',
    targetElement: '#main-content',
    title: 'Welcome to Edeon',
    body: `Edeon is a desktop platform for agrochemical lead optimization with 
           validated Tier-1 prediction models, calibrated uncertainty, and 
           closed-loop molecular design. This 60-second tour will show you the 
           main workflows.`,
    action: { type: 'load_demo_compound', smiles: 'IMIDACLOPRID_SMILES' },
    nextLabel: 'Show me',
  },
  {
    id: 'honeycomb',
    targetElement: '#honeycomb-panel',
    title: 'The Honeycomb',
    body: `Each cell shows a Tier-1 prediction with calibrated 95% confidence 
           intervals. Green = in applicability domain, yellow = borderline, 
           red = out of domain. Where measured data exists, you'll see a 
           🧪 experimental overlay.`,
    nextLabel: 'Continue',
  },
  {
    id: 'fate_gauge',
    targetElement: '#fate-gauge',
    title: 'Environmental Fate',
    body: `Koc, DT50, and GUS leaching index with Monte Carlo uncertainty 
           propagation. The DT50 model uses a heteroscedastic architecture 
           that captures both aleatoric (study-to-study) and epistemic 
           (model) uncertainty separately.`,
    nextLabel: 'Continue',
  },
  {
    id: 'docking',
    targetElement: '#docking-workbench-nav',
    title: 'Docking Workbench',
    body: `Real AutoDock Vina docking with automatic receptor preparation, 
           pocket detection, and ProLIF interaction analysis. Not a 3D 
           visualizer pretending to be docking — actual docking.`,
    action: { type: 'navigate', view: 'docking' },
    nextLabel: 'See generation',
  },
  {
    id: 'generation',
    targetElement: '#generation-workbench-nav',
    title: 'Generation Workbench',
    body: `CReM-dock pipeline for closed-loop molecular design. Generated 
           mutants are scored against the full Tier-1 ecotox + fate + 
           mammalian stack. This combination doesn't exist in any other 
           agrochemistry tool.`,
    nextLabel: 'Finish',
  },
  {
    id: 'knowledge',
    targetElement: '#knowledge-hub-nav',
    title: 'Knowledge Hub',
    body: `Federated search across PPDB, ECOTOX, OpenFoodTox, and ChEMBL, 
           plus a Claude-powered Q&A assistant with citation-grounded 
           answers. Press Cmd+K anytime to access the command palette.`,
    nextLabel: 'Get started',
  },
];
```

**Acceptance:** All 5 steps render correctly with target highlighting; "Continue" advances; navigation actions work; final step closes tour and marks complete.

---

#### Task A4: Tour styles and animations
**File:** `src/shell/OnboardingTour.module.css`

Style the tour overlay using design tokens. Spotlight effect: dim background, highlight target element with subtle pulse animation. Tour card uses `--shadow-overlay`, `--radius-lg`, max-width 420px. Smooth transitions between steps (200ms ease-out).

**Acceptance:** Tour visually polished; works in both light and dark mode.

---

#### Task A5: Tour replay mechanism
**File:** Extend Help menu (added in Group C).

Add menu item "Show tour again" that opens the tour regardless of first-launch status.

**Acceptance:** User can replay tour after dismissal.

---

### Group B — Command Palette (3–4 days)

**Goal:** Cmd+K (Mac) / Ctrl+K (Windows/Linux) opens a searchable launcher for every navigation action and major function in the app.

#### Task B1: Command/shortcut registry
**File:** `src/store/shortcutsRegistry.ts`

```typescript
export interface Command {
  id: string;
  label: string;
  hint?: string;                           // Optional secondary text
  keywords?: string[];                     // Searchable terms not in label
  category: 'navigation' | 'action' | 'workflow' | 'help' | 'settings';
  icon?: ReactNode;
  shortcut?: string;                       // e.g. 'Cmd+N'
  enabled?: () => boolean;                 // Conditional availability
  execute: () => void | Promise<void>;
}

class CommandRegistry {
  private commands = new Map<string, Command>();
  
  register(command: Command): void { ... }
  unregister(id: string): void { ... }
  list(filter?: { category?: string }): Command[] { ... }
  search(query: string): Command[] { ... }  // Fuzzy match over label + keywords
  execute(id: string): Promise<void> { ... }
}

export const commandRegistry = new CommandRegistry();
```

Built-in commands registered at app startup:

```typescript
// Navigation
{ id: 'nav.honeycomb', label: 'Open Honeycomb', category: 'navigation', shortcut: 'Cmd+1' }
{ id: 'nav.qsar', label: 'Open QSAR Studio', category: 'navigation', shortcut: 'Cmd+2' }
{ id: 'nav.docking', label: 'Open Docking Workbench', category: 'navigation', shortcut: 'Cmd+3' }
{ id: 'nav.generation', label: 'Open Generation Workbench', category: 'navigation', shortcut: 'Cmd+4' }
{ id: 'nav.knowledge', label: 'Open Knowledge Hub', category: 'navigation', shortcut: 'Cmd+5' }
{ id: 'nav.reports', label: 'Open Reports', category: 'navigation', shortcut: 'Cmd+6' }
{ id: 'nav.workflows', label: 'Open Workflow Gallery', category: 'navigation', shortcut: 'Cmd+7' }

// Actions
{ id: 'project.new', label: 'New Project', category: 'action', shortcut: 'Cmd+N' }
{ id: 'project.open', label: 'Open Project...', category: 'action', shortcut: 'Cmd+O' }
{ id: 'compound.add', label: 'Add Compound', category: 'action', shortcut: 'Cmd+Shift+A',
  enabled: () => activeProjectId !== null }
{ id: 'compound.predict_all', label: 'Predict all endpoints for current compound', 
  category: 'action', shortcut: 'Cmd+P' }

// Workflows
{ id: 'workflow.w1', label: 'Run W1: Registration Readiness Pre-Screen', category: 'workflow' }
{ id: 'workflow.w2', label: 'Run W2: Pollinator Safety Screen', category: 'workflow' }
// ... etc for W3-W8

// Help
{ id: 'help.tour', label: 'Show onboarding tour', category: 'help' }
{ id: 'help.shortcuts', label: 'Show keyboard shortcuts', category: 'help', shortcut: '?' }
{ id: 'help.about', label: 'About Edeon', category: 'help' }
{ id: 'help.docs', label: 'Open documentation', category: 'help' }

// Settings
{ id: 'settings.open', label: 'Open Settings', category: 'settings', shortcut: 'Cmd+,' }
{ id: 'settings.theme.toggle', label: 'Toggle dark mode', category: 'settings', shortcut: 'Cmd+Shift+L' }
{ id: 'settings.density', label: 'Change UI density', category: 'settings' }
```

**Acceptance:** Registry holds 30+ commands; `search('docking')` returns the docking nav command first; categories filter correctly.

---

#### Task B2: Command palette UI
**File:** `src/shell/CommandPalette.tsx`

Use `cmdk` library:

```typescript
import { Command } from 'cmdk';
import { useCommandRegistry } from '@/store/shortcutsRegistry';

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const registry = useCommandRegistry();
  
  // Cmd+K / Ctrl+K opens
  useKeyboardShortcut('cmd+k', () => setOpen(true));
  useKeyboardShortcut('ctrl+k', () => setOpen(true));
  
  const results = useMemo(() => registry.search(query), [query]);
  
  return (
    <Command.Dialog open={open} onOpenChange={setOpen}>
      <Command.Input placeholder="Type a command or search..." 
                     value={query} onValueChange={setQuery} />
      <Command.List>
        <Command.Empty>No results found.</Command.Empty>
        {Object.entries(groupByCategory(results)).map(([category, items]) => (
          <Command.Group heading={CATEGORY_LABELS[category]}>
            {items.map(cmd => (
              <Command.Item key={cmd.id} 
                            onSelect={() => { cmd.execute(); setOpen(false); }}
                            disabled={cmd.enabled && !cmd.enabled()}>
                {cmd.icon && <Icon>{cmd.icon}</Icon>}
                <span>{cmd.label}</span>
                {cmd.shortcut && <kbd>{cmd.shortcut}</kbd>}
              </Command.Item>
            ))}
          </Command.Group>
        ))}
      </Command.List>
    </Command.Dialog>
  );
}
```

Visual styling using design tokens:
- Backdrop: semi-transparent overlay (`rgba(0,0,0,0.4)` light, `rgba(0,0,0,0.7)` dark)
- Card: centered, 600px wide, max-height 400px, `--shadow-overlay`, `--radius-lg`
- Input: full-width, no border, `--font-size-md`, focused on open
- Items: hover state, selected state (highlighted with `--color-action-primary`)
- Shortcut display: `<kbd>` styled element with subtle background, mono font
- Smooth open/close animation (150ms)

**Acceptance:** Cmd+K opens palette; typing filters in real-time; arrow keys navigate; Enter executes; Escape closes.

---

#### Task B3: Recent commands tracking
**File:** Extend `commandRegistry`.

Track the 10 most recently executed commands. When palette opens with empty query, show recent commands first under "Recent" category.

**Acceptance:** After executing 3 commands, opening palette shows them under "Recent."

---

### Group C — Help/About Panel + Citation Export (3–4 days)

**Goal:** professional "About" panel signaling scientific seriousness, plus one-click citation export for predictions and reports.

#### Task C1: About modal
**File:** `src/shell/AboutModal.tsx`

Triggered by Help menu → "About Edeon" or command palette → `help.about`.

Sections:

**Header:** Edeon logo, version string (e.g., "Edeon 1.0.0 — build 5a3f7b2"), tagline.

**Build info:**
- Application version
- Build commit hash
- Build date
- Platform (e.g., "macOS arm64", "Windows x86_64", "Linux x86_64")
- Python sidecar version

**Models deployed:** Table of every Tier-1 backend with:
- Endpoint name
- Model version
- Training date
- Test set verification status (✓ verified | ⚠ pending)
- Number of training compounds
- Reference paper / dataset

**External integrations:**
- Anthropic API (Claude version if connected)
- OPERA version
- AutoDock Vina version
- CReM ecosystem versions

**Citation block:**
> If you use Edeon in published work, please cite:
> 
> [Author A, Author B] (2026). Edeon: An open-uncertainty platform for agrochemical lead optimization with validated Tier-1 predictions. *Journal of Cheminformatics* (in submission). DOI: pending.
> 
> [Copy citation] [BibTeX] [RIS]

**Licenses block:** List of bundled third-party components with their licenses (Vina Apache 2.0, ProLIF Apache 2.0, RDKit BSD-3, CReM BSD-3, Meeko LGPL-2.1, etc.).

**Support:** Contact email, documentation link, GitHub issues link if open.

**Acceptance:** Modal renders with all sections populated from real system data. No placeholder text.

---

#### Task C2: System info backend
**File:** `python/edeon_app_meta/system_status.py`

IPC command `app_meta_get_system_info()` returning:

```python
class SystemInfo(BaseModel):
    app_version: str
    build_commit: str
    build_date: datetime
    platform: str
    python_version: str
    deployed_models: list[DeployedModelInfo]
    external_integrations: dict[str, str | None]  # Name -> version
    citation_block: str
    licenses: list[LicenseEntry]


class DeployedModelInfo(BaseModel):
    endpoint: str
    model_version: str
    training_date: datetime
    verified: bool
    n_training_compounds: int
    references: list[str]
```

**Acceptance:** IPC returns valid SystemInfo. Models data sourced from model card store.

---

#### Task C3: Citation export button
**File:** `src/components/shared/CitationExportButton.tsx`

Small icon button rendered alongside:
- Any prediction display
- Any report
- Any workflow result
- The About modal

Click opens dropdown with options:
- Copy plain citation
- Copy BibTeX
- Copy RIS
- Copy markdown

Each format generated by `citation_generator.py` backend:

```python
def generate_citation(
    citation_target: Literal["edeon_app", "prediction", "workflow", "report"],
    target_metadata: dict,
    format: Literal["plain", "bibtex", "ris", "markdown"]
) -> str:
    """Generate a properly-formatted citation for the target.
    For predictions: includes model version, prediction value, citation 
    of the original model paper.
    For reports: includes report ID and date, software version.
    """
```

**Acceptance:** Citation button renders in correct locations; each format produces valid output (BibTeX validates, RIS validates).

---

#### Task C4: Help menu accessibility
**File:** Extend top header bar from Group D.

Add a "Help" menu in the header with items:
- Show onboarding tour
- Keyboard shortcuts (`?`)
- About Edeon
- Documentation (opens external URL)
- Report an issue (opens external URL or feedback form)

**Acceptance:** Help menu accessible from header; all items functional.

---

### Group D — Top Header Bar + Status Bar (2–3 days)

**Goal:** persistent header for context, status bar for system health. The professional desktop software cue.

#### Task D1: Top header bar
**File:** `src/shell/TopHeaderBar.tsx`

Layout (left to right):
- Edeon logo (small, clickable → opens About modal)
- Current project dropdown (clickable, switches project)
- Current compound display: 2D mini-thumbnail + name (clickable → opens Inspector)
- Vertical separator
- Global search input (focuses on Cmd+/ or Ctrl+/) — searches across compounds, workflows, knowledge hub
- Flex spacer
- Notification bell (background tasks indicator)
- Help menu
- User/Settings menu
- Theme toggle (sun/moon icon)

Implementation notes:
- Sticky positioned at top, full-width
- 56px height
- Background `--color-surface-base`, border-bottom `--color-border-subtle`
- z-index `--z-sticky`
- Responsive: at narrow widths, collapses some items into overflow menu

```typescript
export function TopHeaderBar() {
  const { activeProject, projects, setActiveProject } = useProjectStore();
  const { selectedCompound } = useUiStore();
  
  return (
    <header className={styles.headerBar}>
      <div className={styles.left}>
        <Logo onClick={openAboutModal} />
        <ProjectDropdown active={activeProject} options={projects}
                         onChange={setActiveProject} />
        {selectedCompound && (
          <CompoundCard compound={selectedCompound} 
                        onClick={() => navigate('/inspector')} />
        )}
      </div>
      <div className={styles.center}>
        <GlobalSearchInput />
      </div>
      <div className={styles.right}>
        <NotificationsButton />
        <HelpMenu />
        <UserMenu />
        <ThemeToggle />
      </div>
    </header>
  );
}
```

**Acceptance:** Header renders consistently across all views; all interactive elements functional; responsive at narrow widths.

---

#### Task D2: Status bar
**File:** `src/shell/StatusBar.tsx`

Layout (left to right):
- T1 backend health: `T1: 13✓` (green) or `T1: 9/13 ⚠` (yellow if any failed)
- OPERA status: `OPERA: ✓` or `OPERA: offline`
- Claude API status: `Claude: ✓` or `Claude: not connected`
- Vertical separator
- CPU usage: `CPU: 23%`
- Memory usage: `MEM: 1.2GB`
- Flex spacer
- Background tasks: `Tasks: 2 running` (clickable, shows task list)
- Last sync/status timestamp

Implementation:
- Sticky at bottom, full-width
- 28px height
- Smaller font (`--font-size-xs`)
- Background `--color-surface-raised`
- Updates every 5 seconds via IPC poll or event subscription

```typescript
export function StatusBar() {
  const status = useSystemStatus({ pollIntervalMs: 5000 });
  
  return (
    <footer className={styles.statusBar}>
      <StatusIndicator label="T1" value={`${status.t1_loaded}/${status.t1_total}`}
                        status={status.t1_all_loaded ? 'good' : 'moderate'} />
      <StatusIndicator label="OPERA" status={status.opera_available ? 'good' : 'unknown'} />
      <StatusIndicator label="Claude" status={status.claude_api_configured ? 'good' : 'unknown'} />
      <Separator />
      <ResourceIndicator label="CPU" value={status.cpu_percent} />
      <ResourceIndicator label="MEM" value={status.memory_mb} />
      <FlexSpacer />
      {status.background_tasks_count > 0 && (
        <BackgroundTasksButton count={status.background_tasks_count} />
      )}
    </footer>
  );
}
```

**Acceptance:** Status bar renders; updates every 5s; indicators reflect actual system state.

---

#### Task D3: SystemStatus IPC backend
**File:** Extend `python/edeon_app_meta/system_status.py`.

IPC command `app_meta_get_status()` returning:

```python
class SystemStatus(BaseModel):
    t1_loaded: int
    t1_total: int
    t1_all_loaded: bool
    opera_available: bool
    claude_api_configured: bool
    cpu_percent: float
    memory_mb: int
    background_tasks_count: int
    background_tasks: list[BackgroundTaskSummary]
    last_updated: datetime
```

Uses `psutil` for system resources, queries backend registry for backend status.

**Acceptance:** Returns valid status data; numbers update.

---

### Group E — Verification Badges & Trust Signals (3–4 days)

**Goal:** make the Workstream A verification investment visible to users and evaluators.

#### Task E1: VerificationBadge component
**File:** `src/components/shared/VerificationBadge.tsx`

```typescript
interface VerificationBadgeProps {
  endpoint: string;
  verified: boolean;
  empirical_coverage?: number;        // e.g., 0.952
  test_set_size?: number;
  verification_date?: Date;
  variant?: 'compact' | 'expanded';
}

export function VerificationBadge({ ... }: VerificationBadgeProps) {
  if (!verified) return null;
  
  return (
    <Tooltip content={
      <div>
        <strong>Verified Tier-1 model</strong>
        <p>Empirical 95% CI coverage: {(empirical_coverage * 100).toFixed(1)}%</p>
        <p>Test set: {test_set_size} held-out compounds</p>
        <p>Verified: {formatDate(verification_date)}</p>
        <a href="#" onClick={openVerificationReport}>View report →</a>
      </div>
    }>
      <span className={`${styles.badge} ${styles[variant]}`}>
        <CheckShieldIcon /> Verified
      </span>
    </Tooltip>
  );
}
```

Visual style: small pill, green background `--color-status-good-bg`, green text `--color-status-good`, checkmark shield icon. On hover shows detailed tooltip.

**Acceptance:** Badge renders in compact and expanded variants; tooltip shows real verification data.

---

#### Task E2: Integration into model card viewer
**File:** Extend `ModelCardViewer.tsx`.

For every Tier-1 backend, render the VerificationBadge in `expanded` variant near the top of the card. Pulls verification data from the Workstream A reports.

**Acceptance:** Every T1 model card displays verification badge with real numbers.

---

#### Task E3: Integration into Inspector predictions
**File:** Extend `PredictionDisplay.tsx`.

For every Tier-1 prediction display, render a small VerificationBadge in `compact` variant alongside the tier badge.

**Acceptance:** Inspector shows verification badge for each T1 prediction.

---

#### Task E4: ReproducibilityInfo popover
**File:** `src/components/shared/ReproducibilityInfo.tsx`

Small `ℹ️` icon rendered alongside any prediction, workflow result, or report. Click opens popover with:
- Model version
- Model checkpoint hash
- Training dataset version
- Training dataset URL
- Random seed
- Software version
- Prediction timestamp
- Conformal calibration version
- Applicability domain version

Provides "Copy as JSON" button for full provenance export.

**Acceptance:** Reproducibility info popover renders consistent metadata across all prediction surfaces.

---

#### Task E5: Verification report viewer
**File:** `src/views/VerificationReportView.tsx` (new view, accessible via "View report" link in badge tooltips)

Displays the contents of `docs/verification/SUMMARY.md` and per-endpoint reports as formatted HTML. Shows:
- Overall verification status
- Per-endpoint pass/fail table
- Coverage metrics
- DT50 NLL and σ correlation values
- Test set sizes
- Verification dates

**Acceptance:** Verification report view accessible and displays current verification state.

---

### P0 — Workstream Acceptance

P0 is complete when ALL:
1. Design tokens established and documented
2. First-launch tour works end-to-end with all 5 steps
3. Command palette opens on Cmd+K with 30+ commands
4. About modal displays comprehensive system info with citations
5. Top header bar present on every view
6. Status bar present on every view, updates every 5s
7. Verification badges visible on T1 predictions and model cards
8. Reproducibility info accessible on every prediction surface
9. CI passes; no regressions in existing tests

---

## 6. Priority P1 — Workflow Lubrication (2–3 weeks)

### Group F — Empty States & Contextual Help (3–4 days)

#### Task F1: EmptyState component
**File:** `src/components/shared/EmptyState.tsx`

```typescript
interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description: string;
  primaryAction?: { label: string; onClick: () => void };
  secondaryAction?: { label: string; onClick: () => void };
  illustration?: ReactNode;
}
```

Visual style: centered, large icon, title, description, optional action buttons. Used throughout the app wherever a panel can be empty.

**Acceptance:** Component renders consistently; supports all variants.

---

#### Task F2: Apply empty states across the app
**Action:** Audit every view for empty/uninitialized states. Replace blank panels with EmptyState components:

| View | When | Empty state content |
|---|---|---|
| Honeycomb | No compound selected | "Select a compound to see predictions" + "Try imidacloprid" button |
| Inspector | No compound | "No compound loaded" + "Add compound" / "Load demo" |
| Docking Workbench | No receptor | "Load a receptor to begin docking" + receptor options |
| Generation Workbench | No parent | "Provide a starting compound to generate analogs" |
| Knowledge Hub Chat | No conversations | "Ask a question about pesticides, regulations, or any compound" |
| Reports | No reports yet | "Run a workflow to generate your first report" |
| Workflow Gallery | No history | "Workflows you run will appear here" |
| QSAR Studio | No model loaded | "Train or load a model to begin" |

**Acceptance:** Every view has a meaningful empty state.

---

#### Task F3: ContextualHelp component
**File:** `src/components/shared/ContextualHelp.tsx`

Small `?` icon that opens a popover with longer explanatory content:

```typescript
interface ContextualHelpProps {
  topicId: string;           // Maps to entry in help_content.json
  position?: 'top' | 'right' | 'bottom' | 'left';
  iconSize?: 'sm' | 'md';
}
```

Help content lives in `src/content/help/help_content.json`:

```json
{
  "honeycomb.cell": {
    "title": "Honeycomb cell",
    "body": "Each cell shows a Tier-1 prediction with calibrated 95% confidence interval. Color indicates applicability domain: green = in domain, yellow = borderline, red = out of domain. Numbers below show predicted value with units.",
    "learn_more": "docs/HONEYCOMB.md"
  },
  "fate.gus": {
    "title": "Groundwater Ubiquity Score (GUS)",
    "body": "GUS estimates leaching risk from soil DT50 and Koc. Edeon propagates uncertainty from both inputs via Monte Carlo sampling to give a probability distribution over leaching class (Non-leacher / Transition / Leacher).",
    "learn_more": "docs/GUS_METHODOLOGY.md"
  },
  "docking.vina_score": {
    "title": "Vina docking score",
    "body": "AutoDock Vina's score is an empirical estimate of binding free energy in kcal/mol. It is not a measured K_d or IC50. Use for relative comparison of poses or compounds, not absolute affinity.",
    "learn_more": "docs/DOCKING_PROTOCOL.md"
  },
  // ... at least 30 entries covering key UI elements
}
```

**Acceptance:** Help icons render consistently; popovers show real content; "learn more" links navigate to docs.

---

#### Task F4: Apply contextual help across the app
**Action:** Add `?` icons next to:
- Each honeycomb cell type (bee, fish, etc.)
- Fate gauge metrics (Koc, DT50, GUS)
- Toxicity panel items
- Docking workbench controls (exhaustiveness, box config)
- Generation workbench parameters
- MPO scoring weights
- Applicability domain indicators
- Tier badges
- At least 30 individual placements

**Acceptance:** Help icons visible at all 30+ locations; content populated.

---

### Group G — Keyboard Shortcuts Discoverability (2 days)

#### Task G1: Shortcuts registry consolidation
**File:** `src/content/help/shortcuts.json`

Consolidate all keyboard shortcuts into a single registry organized by category:

```json
{
  "Navigation": [
    { "keys": "Cmd+1", "description": "Open Honeycomb" },
    { "keys": "Cmd+2", "description": "Open QSAR Studio" },
    // ...
  ],
  "Actions": [
    { "keys": "Cmd+N", "description": "New project" },
    { "keys": "Cmd+O", "description": "Open project" },
    // ...
  ],
  "Help": [
    { "keys": "?", "description": "Show this overlay" },
    { "keys": "Cmd+K", "description": "Open command palette" },
    // ...
  ]
}
```

**Acceptance:** All shortcuts documented in single source.

---

#### Task G2: Shortcuts overlay
**File:** `src/shell/KeyboardShortcutsOverlay.tsx`

Pressing `?` (when not in an input field) opens a translucent overlay showing all keyboard shortcuts grouped by category. Escape closes.

Visual style:
- Semi-transparent background
- Centered modal-like panel, 700px wide
- Three columns of shortcuts grouped by category
- Each shortcut: `<kbd>` styled keys + description
- Search input at top filters shortcuts in real-time

**Acceptance:** Pressing `?` opens overlay; shortcuts categorized; search filters; Escape closes.

---

#### Task G3: Shortcut hints in UI
**Action:** Throughout the app, add subtle shortcut hints next to actions when shortcuts exist. Example: the "Dock" button in the docking workbench shows `Cmd+D` next to its label in a subtle style.

**Acceptance:** At least 10 prominent actions show their shortcut hints.

---

### Group H — Citation Export (already in P0 Group C, expanded)

#### Task H1: Bulk citation export
**File:** Extend Reports view.

For any report with multiple compounds/predictions, add a "Export all citations" button that produces:
- A single BibTeX file with entries for every cited model
- A single RIS file
- A single markdown file with all citations

**Acceptance:** Bulk export produces valid files.

---

### Group I — Progress Indicators Standardization (3–4 days)

#### Task I1: ProgressIndicator component
**File:** `src/components/shared/ProgressIndicator.tsx`

```typescript
interface ProgressIndicatorProps {
  variant: 'determinate' | 'indeterminate';
  value?: number;                // 0-100 for determinate
  label?: string;                // e.g., "Docking pose 3 of 9"
  estimated_remaining_sec?: number;
  elapsed_sec?: number;
  cancelable?: boolean;
  onCancel?: () => void;
  size?: 'sm' | 'md' | 'lg';
}
```

Renders a progress bar with label, ETA, and optional cancel button.

**Acceptance:** Component supports all variants; renders cleanly.

---

#### Task I2: Apply standardized progress to long operations
**Action:** Audit every long operation. Replace generic spinners with ProgressIndicator showing real progress where possible:

- Receptor preparation (5-30s) — determinate with steps
- Ligand preparation (2-10s) — determinate with steps
- fpocket detection (10-60s) — determinate
- Vina docking (30-120s) — determinate with pose progress
- CReM mutation generation (10-30s) — determinate
- CReM-dock pipeline (minutes) — determinate with iteration progress
- OPERA prediction (5-15s per compound) — determinate with compound progress
- W1-W8 workflow execution — determinate with step progress
- Knowledge Hub embedding indexing — determinate with batch progress
- QSAR model training — determinate with epoch progress

**Acceptance:** All long operations show progress indicators with ETA where possible.

---

### Group J — Background Tasks Panel (2 days)

#### Task J1: Background tasks UI
**File:** `src/shell/BackgroundTasksPanel.tsx`

Triggered from the status bar's task indicator. Slide-out panel showing:
- All currently running background tasks
- Each task: name, type, start time, progress, cancel button
- Completed tasks (last 10) with completion time and link to results

**Acceptance:** Panel renders; tasks update in real-time.

---

### P1 — Workstream Acceptance

P1 is complete when ALL P0 is complete AND:
1. Every view has appropriate empty states
2. 30+ contextual help popovers throughout the app
3. `?` opens shortcuts overlay
4. Shortcut hints visible on prominent actions
5. Bulk citation export works
6. All long operations use standardized ProgressIndicator
7. Background tasks panel functional

---

## 7. Priority P2 — Aesthetic Polish (2–3 weeks)

### Group K — Dark Mode (3–5 days)

#### Task K1: Theme provider
**File:** `src/shell/ThemeProvider.tsx`

```typescript
type Theme = 'light' | 'dark' | 'system';

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useThemeStore();
  
  useEffect(() => {
    const effectiveTheme = theme === 'system' 
      ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : theme;
    document.documentElement.setAttribute('data-theme', effectiveTheme);
  }, [theme]);
  
  return <>{children}</>;
}
```

State persisted in settings store.

**Acceptance:** Theme toggle works; persists across launches; respects system preference.

---

#### Task K2: Dark mode token application
**Action:** Verify every component renders correctly in dark mode. Audit specifically:
- All chart components (Recharts) — provide dark mode themes
- 3D viewer (NGL.js) — match background to surface color
- Code blocks and JSON displays
- Tooltips and popovers
- Modal overlays

**Acceptance:** Every view renders correctly in dark mode.

---

#### Task K3: Dark mode toggle in header
**File:** Extend `TopHeaderBar.tsx`.

Sun/moon icon button toggles between light/dark/system. Click cycles through; long-press or right-click opens preference selection.

**Acceptance:** Toggle works smoothly.

---

### Group L — Density Toggle (2 days)

#### Task L1: Density system
**File:** `src/styles/density/`

Three density modes affecting:
- Spacing scale multipliers
- Font sizes
- Component heights (rows, buttons, inputs)

```css
[data-density="compact"] {
  --space-multiplier: 0.75;
  --font-size-base: 12px;
  --row-height: 28px;
}
[data-density="default"] { /* uses base tokens */ }
[data-density="comfortable"] {
  --space-multiplier: 1.25;
  --font-size-base: 15px;
  --row-height: 44px;
}
```

**Acceptance:** Density toggle changes UI density consistently.

---

#### Task L2: Density toggle in settings
**File:** Extend Settings view.

Add density selector with three options. Live preview.

**Acceptance:** Density change affects all views.

---

### Group M — Visual Consistency Audit (5–7 days)

This is the most important P2 work — bringing existing views to uniform quality.

#### Task M1: Screenshot audit
**Action:** Capture screenshots of every major view in the app. Print them on a single document. Identify inconsistencies:
- Differing button styles
- Differing card border-radius
- Differing spacing
- Differing color usage
- Differing typography

Document findings in `docs/UI_UX_POLISH_NOTES.md`.

**Acceptance:** Audit document committed.

---

#### Task M2: Component-by-component alignment
**Action:** For each inconsistency identified in M1, decide on the canonical version and migrate other usages to match. Priority order:
- Card / panel containers
- Buttons (primary, secondary, ghost)
- Inputs (text, select, checkbox)
- Badges and pills
- Tables and lists
- Modals

**Acceptance:** Screenshot audit redone after migration; no significant inconsistencies remain.

---

#### Task M3: Icon system consolidation
**Action:** If multiple icon libraries are used, consolidate to one (recommended: `lucide-react`). Replace all icon usages.

**Acceptance:** Single icon library across the app.

---

#### Task M4: Animation and transition standardization
**Action:** Define animation tokens:

```css
:root {
  --transition-fast: 100ms ease-out;
  --transition-default: 200ms ease-out;
  --transition-slow: 350ms ease-out;
  --easing-default: cubic-bezier(0.4, 0, 0.2, 1);
}
```

Apply consistently to:
- Modal open/close
- Dropdown open/close
- Tab transitions
- Card hover states
- Button states

**Acceptance:** Animations feel cohesive across the app.

---

### P2 — Workstream Acceptance

P2 is complete when ALL P0 and P1 are complete AND:
1. Dark mode works across every view
2. Density toggle functional
3. Visual consistency audit complete
4. No significant inconsistencies between views
5. Icon system unified
6. Animations standardized

---

## 8. Cross-Cutting Tasks

### X1: Accessibility audit
**File:** `docs/ACCESSIBILITY_AUDIT.md`

Run automated accessibility tests using `axe-core` or similar. Document:
- WCAG AA compliance status
- Keyboard navigation paths
- Screen reader compatibility
- Color contrast ratios

Fix critical issues identified.

**Acceptance:** All P0 components pass automated accessibility checks; documented.

---

### X2: Visual regression CI
**File:** `.github/workflows/ui_ux_lint.yml`

Set up Playwright-based visual regression testing for key views. On each PR, capture screenshots and compare against baseline.

**Acceptance:** Visual regression CI passes.

---

### X3: User documentation
**Files:**
- `docs/KEYBOARD_SHORTCUTS.md`
- `docs/ONBOARDING_TOUR_SCRIPT.md`
- `docs/CITATION_FORMATS.md`
- `docs/DESIGN_TOKENS.md`

User-facing documentation for each new feature.

**Acceptance:** Documents committed.

---

### X4: Settings panel updates
**File:** Extend Settings view.

Add new sections:
- **Appearance**: theme (light/dark/system), density (compact/default/comfortable)
- **Onboarding**: "Show tour on next launch" checkbox, "Show tour now" button
- **Notifications**: enable/disable system notifications for background tasks
- **Shortcuts**: link to keyboard shortcuts overlay

**Acceptance:** Settings panel updated with new sections.

---

## 9. Acceptance Criteria for Plan Complete

Plan is complete when:

1. P0 (Critical Polish) all groups passing
2. P1 (Workflow Lubrication) all groups passing
3. P2 (Aesthetic Polish) all groups passing
4. Cross-cutting accessibility, regression, docs complete
5. No existing tests regressed
6. TypeScript strict checks still passing
7. Visual regression CI passing
8. Settings panel updated
9. All documentation committed

If time permits stopping at P0 only: must still cover X1 (accessibility) and X3 (documentation) at least for P0 features.

---

## 10. Out of Scope

Explicitly **do not**:

- Build new scientific features
- Modify backend model behavior
- Add new tools or workflows (the existing W1-W8 are sufficient)
- Implement multi-user features
- Implement cloud sync
- Build mobile/responsive layouts
- Replace existing libraries (NGL.js, Recharts, etc.) unless absolutely necessary
- Implement internationalization beyond preparing tokens for future i18n
- Add new ML models or endpoints

---

## 11. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Design token migration breaks existing components | Pre-migration audit (Section 4.2); migrate incrementally; visual regression CI catches regressions |
| `cmdk` library doesn't integrate cleanly | Fall back to custom command palette implementation; `cmdk` is small enough to be replaced |
| `driver.js` conflicts with existing modals | Test thoroughly with existing modals; alternative: `react-joyride` |
| Tour breaks when app is updated and target elements change | Tour steps use stable element IDs; CI test verifies all target elements exist on every build |
| Dark mode breaks chart libraries | Audit Recharts dark mode; provide custom themes; document any limitations |
| Visual consistency audit identifies massive amount of work | Prioritize high-traffic views first; P2 is explicitly optional |
| Status bar polling impacts performance | Cache aggressively; only poll when status bar visible; use system events when possible |
| Help content gets stale | Keep help_content.json in sync with feature changes; treat as code |
| Existing keyboard shortcuts conflict with new ones | Audit existing shortcuts first; document conflicts; resolve before introducing new |

---

## 12. Conventions

- All new components use TypeScript with explicit prop types
- All new components must render in both light and dark mode from initial implementation
- All new components must be keyboard accessible
- All new components must include unit tests (minimum: renders without error, props work as expected)
- All user-visible strings extracted to constants (preparing for future i18n)
- All new IPC commands documented with pydantic models
- Random animation timing: use defined animation tokens, no magic numbers
- File organization: shell components in `src/shell/`, shared in `src/components/shared/`
- No inline styles; all styling via CSS modules or token-based classes

---

## 13. Handoff Notes

After this plan completes:

- **First-impression quality** moves Edeon into "feels professional within 60 seconds" territory.
- **Trust signals** (verification badges, citation export, about modal substance, reproducibility info) make the technical investment visible to evaluators.
- **Workflow lubrication** (command palette, contextual help, empty states, shortcuts) reduces abandonment during exploration.
- **Visual consistency** lifts overall impression from "collection of capabilities" to "coherent product."

This work is **not optional for commercial conversations beyond academic and small-startup segments**. The regulatory consultancy, mid-tier agrochem, and any enterprise procurement evaluation will judge by these surface qualities even when the technical underpinnings are sound.

---

## 14. Deviation Log

Maintain `docs/UI_UX_POLISH_NOTES.md` recording:
- Design token decisions made during pre-implementation audit
- `cmdk` vs custom command palette decision
- `driver.js` vs `react-joyride` decision
- Per-view consistency issues identified and resolutions
- Accessibility issues found and fixes
- Performance impact measurements
- Components that proved especially difficult to dark-mode

---

**End of UI/UX Polish Implementation Plan.**
