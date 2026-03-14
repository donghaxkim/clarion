# LiveKit Agent Orb — Design Spec
**Date:** 2026-03-11
**Project:** Clarion (experience/ — Next.js 14)
**Status:** Approved

---

## Overview

Add a floating voice agent visualizer ("Agent Orb") to the Clarion evidence canvas. The orb sits bottom-left, renders `AgentAudioVisualizerAura` from the LiveKit Agents UI registry, and cycles through mock agent states on click. Zoom controls move from bottom-left to bottom-right.

---

## Goals

- Render `AgentAudioVisualizerAura` with Clarion's `#1FD5F9` accent color in the bottom-left canvas corner
- Support mock `AgentState.Disconnected | Listening | Speaking` cycling (click to advance) without a live LiveKit server
- Move `ZoomControls` to bottom-right
- Wire up `next-themes` so `themeMode` prop works correctly
- Design so real LiveKit connection is a one-line swap later

---

## Dependencies

### npm packages (install via `npm install`)
```
@livekit/components-react@^2   — provides AgentState enum; verified member names below
livekit-client                 — peer dependency of above
next-themes                    — provides useTheme / ThemeProvider
```

Pin `@livekit/components-react@^2`. The `AgentState` enum in v2.x has these members (verified):
- `AgentState.Disconnected` — use as initial/idle state
- `AgentState.Listening`
- `AgentState.Speaking`
- `AgentState.Thinking` — skip in mock cycle

Mock cycle: `Disconnected → Listening → Speaking → Disconnected`

### Shadcn-scaffolded component
The visualizer component comes from the LiveKit Agents UI registry, not from the npm package:
```
npx shadcn@latest add @agents-ui/agent-audio-visualizer-aura --registry https://agents-ui.livekit.io/r
```
Places source at `src/components/agents-ui/agent-audio-visualizer-aura/`.

**After installation, verify from the generated source:**
- Exact prop names (expected: `size`, `color`, `colorShift`, `state`, `themeMode`, `className`)
- Valid `themeMode` values (expected: `'light' | 'dark'` — `'dark'` matches Clarion's theme)

---

## No Mock Context Needed

`AgentAudioVisualizerAura` accepts `state` as a **direct prop**. The demo calls `useAgent()` to get state and forward it, but the visualizer is stateless. `AgentOrb` owns local `mockState` and passes it directly — no LiveKit room context required.

---

## New Files

### `src/components/agent/AgentOrb.tsx`
`'use client'` component. Named export: `export function AgentOrb()`. No external props.

```tsx
'use client';
import { useState } from 'react';
import { AgentState } from '@livekit/components-react';
import { useTheme } from 'next-themes';
// After shadcn install, check the generated directory for the entry file.
// It is typically an index file; if not, adjust the path to the actual filename.
import { AgentAudioVisualizerAura } from '@/components/agents-ui/agent-audio-visualizer-aura';

const CYCLE: AgentState[] = [
  AgentState.Disconnected,
  AgentState.Listening,
  AgentState.Speaking,
];

export function AgentOrb() {
  const [stateIndex, setStateIndex] = useState(0);
  const { resolvedTheme } = useTheme();

  const mockState = CYCLE[stateIndex];
  // Use ternary to satisfy 'light' | 'dark' union type — resolvedTheme is string | undefined
  const themeMode = resolvedTheme === 'light' ? 'light' : 'dark';

  function handleClick() {
    setStateIndex((i) => (i + 1) % CYCLE.length);
  }

  return (
    <div onClick={handleClick} style={{ cursor: 'pointer' }}>
      <AgentAudioVisualizerAura
        state={mockState}
        color="#1FD5F9"
        colorShift={1.95}   // controls hue shift of the aura; valid range ~0–3; remove if prop not present
        size="xl"
        themeMode={themeMode}
        className="aspect-square w-full"
      />
      {/* Dev label — remove when going live */}
      <div style={{ textAlign: 'center', fontSize: '10px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
        {AgentState[mockState]}
      </div>
    </div>
  );
}
```

> This is a template — confirm all prop names from the generated source after shadcn install. Remove any props that don't exist in the generated component.

### `src/app/providers.tsx`
Co-located with `layout.tsx`. Required because `layout.tsx` is a Server Component (exports `metadata`) and cannot be made a client component:

```tsx
'use client';
import { ThemeProvider } from 'next-themes';
export function Providers({ children }: { children: React.ReactNode }) {
  return <ThemeProvider attribute="class" defaultTheme="dark">{children}</ThemeProvider>;
}
```

---

## Modified Files

### `tailwind.config.ts`
Add `darkMode: 'class'` to the config object. Required for `next-themes` class injection to work with Tailwind utilities:
```ts
const config: Config = {
  darkMode: 'class',
  content: [...],
  // ...
};
```
Clarion currently uses CSS variables for all theming, so this addition is additive and does not break existing styles.

### `layout.tsx`
Two changes:

1. Add `suppressHydrationWarning` to `<html>` — required by `next-themes` to suppress the expected server/client class mismatch warning:
```tsx
<html lang="en" suppressHydrationWarning>
```

2. Import `Providers` and wrap `{children}`:
```tsx
import { Providers } from './providers';
// ...
<body><Providers>{children}</Providers></body>
```

### `ZoomControls.tsx`
**Replace** `left: '20px'` **with** `right: '20px'` (remove `left`, add `right` — do not keep both).

`ZoomControls` must remain inside `<ReactFlow>` — it calls `useReactFlow()` and `useViewport()`, which require the ReactFlow provider context. `<ReactFlow>` renders direct children in a full-width/height `position: relative` internal overlay, so `position: absolute, right: '20px'` works correctly.

### `EvidenceCanvas.tsx`
Two changes, both inside `EvidenceCanvasInner` (the private inner function, not the exported wrapper):

**1. Dynamic import** (add near top of file):
```tsx
import dynamic from 'next/dynamic';
const AgentOrb = dynamic(
  () => import('@/components/agent/AgentOrb').then(m => m.AgentOrb),
  { ssr: false, loading: () => null }
);
```

**2. Render `AgentOrb`** inside the `wrapperRef` div (the outermost `<div>` in `EvidenceCanvasInner`, the one with `{...dropHandlers}`), **after** the `{showAnalyzeWave && ...}` block, as the last child of that div, **outside** `<ReactFlow>`. Both `ZoomControls` (inside ReactFlow's internal overlay) and this `AgentOrb` div (in `wrapperRef`) are positioned relative to the same `wrapperRef` container; `zIndex: 10` on the orb wrapper is sufficient since ReactFlow does not create a higher stacking context:
```tsx
{/* Agent Orb */}
<div style={{ position: 'absolute', bottom: '24px', left: '20px', zIndex: 10, width: '80px' }}>
  <AgentOrb />
</div>
```
`width: '80px'` is required — the visualizer uses `aspect-square w-full` which collapses to zero without a defined parent width. Adjust if desired.

### Install packages
Run `npm install` — this updates `package.json` automatically:
```
npm install @livekit/components-react livekit-client next-themes
```
Do not manually edit `package.json`.

---

## State Flow

```
User clicks AgentOrb
  → setMockState cycles (Disconnected → Listening → Speaking → Disconnected)
  → AgentAudioVisualizerAura receives new state prop
  → Aura animation responds
```

---

## Audio / Browser API Notes

`AgentAudioVisualizerAura` is visual-only when `state` is passed as a prop with no live LiveKit room. No `AudioContext` or `getUserMedia` is initialized.

---

## Future: Real LiveKit

When connecting a real backend:
1. Inside `EvidenceCanvas.tsx`, wrap the `<EvidenceCanvasInner />` JSX (which is inside `EvidenceCanvas`'s `return`) with `<LiveKitRoom url={...} token={...}>`
2. In `AgentOrb`, replace `mockState` and the click handler with `const { state } = useAgent()`
3. Remove dev label

---

## Out of Scope

- Real LiveKit server / token endpoint
- Microphone permission handling
- Text transcript display
- Narrow canvas / mobile layout (AgentOrb and ZoomControls may visually overlap at very narrow widths — acceptable for now)
