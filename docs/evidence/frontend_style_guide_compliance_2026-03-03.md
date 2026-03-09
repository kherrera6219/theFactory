# Frontend Style Guide Compliance — Implementation Evidence (2026-03-03)

## Objective
Implement the remaining frontend items from the compliance audit in parallel with Codex's
WebSocket/SSE, Smelt-cycle, and ADR work:
1. Fix typography mismatch (Style Guide §4)
2. Implement dark SLATE + Refinery Violet color system (Style Guide §2‒§3)
3. Add WebSocket reconnect banner (Frontend Design §8, AC-18)
4. Add responsive breakpoints 1440px + 1024px (Frontend Design §12)

## Discovery Notes
- PM Agent conversational UI (`chat/page.tsx`, 437 lines) was confirmed **already fully implemented** — excluded from scope.
- `globals.css` was 1011 lines of light-mode warm-gradient CSS; required a complete variable rewrite.
- `layout.tsx` used `Space_Grotesk` and `IBM_Plex_Mono` instead of the spec-required `Inter` + `JetBrains Mono`.

## Implementation

### Files Modified

| File | Change |
|------|--------|
| `apps/mission-control/app/layout.tsx` | `Space_Grotesk` → `Inter`, `IBM_Plex_Mono` → `JetBrains_Mono`, metadata title updated |
| `apps/mission-control/app/globals.css` | Full dark-mode rewrite: 31-token CSS variable system, all 1011 lines updated to reference dark tokens, reconnect banner CSS + animations appended |
| `apps/mission-control/app/(shell)/layout.tsx` | Imported and wired `ReconnectBanner` (hidden by default, ready for SSE state) |

### Files Created

| File | Purpose |
|------|---------|
| `apps/mission-control/app/components/reconnect-banner.tsx` | Accessible `role="alert"` banner with amber/red modes for retrying/stale connection states |

### CSS Variable System (Style Guide §2)

```
--bg:            #0F172A   (SLATE — primary background)
--bg-surface:    #1E293B   (SLATE-800 — panels)
--bg-elevated:   #253347   (elevated cards, hover targets)
--ink:           #F1F5F9   (near-white body text)
--ink-muted:     #94A3B8   (SLATE-400 muted)
--accent:        #8B5CF6   (Refinery Violet)
--accent-strong: #7C3AED
--accent-dim:    #6D28D9
--accent-glow:   rgba(139,92,246,0.15)
--success:       #10B981   (+ -bg variant)
--danger:        #EF4444   (+ -bg variant)
--warning:       #F59E0B   (+ -bg variant)
--border:        #334155   (SLATE-700)
--border-strong: #475569   (SLATE-600)
--ring:          rgba(139,92,246,0.5)
```

### Responsive Breakpoints Added

| Breakpoint | Change |
|-----------|--------|
| `min-width: 1440px` | Page width 1320px, shell sidebar 300px, KPI grid 4 columns |
| `max-width: 1024px` | Single-column page, mission-console collapses |
| `max-width: 920px` | (pre-existing) Sidebar collapse, header unstick |
| `max-width: 640px` | (pre-existing) Panel padding, hero collapse |

### Accessibility

- `-webkit-backdrop-filter` added alongside `backdrop-filter` on shell header (Safari 9+ support)
- `ReconnectBanner` uses `role="alert"`, `aria-live="assertive"`, `aria-atomic="true"`
- Reduced-motion rule already present in CSS — banner animation respects it
- Focus ring color updated to Refinery Violet `--ring` (sufficient contrast on dark bg)

## Validation

All checks run immediately after implementation:

```
1. npx tsc --noEmit             → EXIT 0 (no TypeScript errors)
2. npm run lint                 → EXIT 0 (ESLint clean)
3. npm run test -- --run        → 16/16 tests passing (2 test files)
```

No regressions introduced.

## What This Enables for Codex

The `ReconnectBanner` component is pre-wired in `(shell)/layout.tsx` with `isVisible={false}`.
When Codex implements SSE/WebSocket transport, it can drive the banner by:
1. Lifting connection state into context or a custom hook
2. Passing `isVisible={connectionStatus !== 'live'}` and `status={connectionStatus}` to the banner

The `connection-chip` CSS classes (idle/live/retrying/stale) in `globals.css` are also dark-themed
and ready for the status bar footer to reflect live SSE state.
