---
name: react-performance
description: Optimize React rendering performance the right way: useMemo/useCallback with judgment, memoizing whole components, avoiding unnecessary re-renders, React.lazy code splitting, profiling with the React DevTools Profiler, and knowing when NOT to optimize. Use when the user asks how to make a React app faster, avoid re-renders, use memo/useMemo/useCallback correctly, split bundles, lazy load components, or profile React performance. Triggers on "performance", "re-render", "useMemo", "useCallback", "React.memo", "lazy loading", "code splitting", "React Profiler", "avoid re-render".
---

# React — Performance

Performance work starts with **measurement**, not guessing. Default React
rendering is already fast; premature memoization adds complexity and bugs.

## Golden Rules

1. **Profile first, optimize second.** Use the **React DevTools Profiler**
   (Record why each component rendered) or `console.log` count in a render to
   find the actual bottleneck before touching `memo`/`useMemo`.
2. **Optimize for production.** Only wrap when it provably prevents wasted
   renders of an expensive component.
3. **Most re-renders are fine.** React only re-renders the component whose
   state changed plus descendants — cheap reconciliation is normal.
4. **Never micro-optimize.** Wrapping every handler in `useCallback` or every
   value in `useMemo` is a code smell, not a performance win.

## Where Re-Renders Come From

A component re-renders when: its **props change**, its **state changes**, or a
**context it consumes** changes. Because props are often fresh objects/arrows
each render, children see "new" props even when nothing meaningful changed.

## useMemo — cache expensive computations

Use it to **skip expensive re-computation** of derived data on re-renders.

```tsx
function Report({ rows }: { rows: Row[] }) {
  const stats = useMemo(
    () => computeExpensiveStats(rows),
    [rows] // recompute only when rows change
  )
  return <Chart data={stats} />
}
```

- Only for **genuinely expensive** work (filtering thousands of items,
  JSON-stringify big structures, non-trivial math), or when the memoized value
  is itself used as a dependency of `useEffect`/`useMemo`/`useCallback`.
- If the computation is cheap (a filter on a 50-item list), just compute it
  inline each render.
- Dependencies must be exhaustive — a stale `rows` in the closure causes bugs.

## useCallback — cache stable function references

Use it when a stable function identity matters: it's passed to a **memoized
child**, used as a dependency of an effect, or in a `Context` value.

```tsx
const handleChange = useCallback((v: string) => setValue(v), [])
```

- `useCallback` does **not** make the handler faster — it preserves identity
  so `React.memo` children skip re-rendering and effects don't re-run.
- Only wrap when the consumer is `memo`-wrapped or the function is in an
  effect/context dependency array. Otherwise write plain functions.
- If you pass an inline arrow to a non-memoized child, the wrapper is wasted.

## React.memo — skip re-renders of a whole component

Wrap a component to skip re-rendering when its props are unchanged
(shallow-equal) and its own state/hooks didn't change.

```tsx
const TodoItem = memo(function TodoItem({ todo, onToggle }) {
  return (
    <li>
      <input type="checkbox" checked={todo.done} onChange={() => onToggle(todo.id)} />
      {todo.text}
    </li>
  )
})
```

- Worth it for **large lists of stable, expensive items** where parents
  re-render often. Pair with stable `useCallback` callbacks and stable item
  props.
- **Not** worth it for small/cheap components — the memo comparison costs as
  much as the render.
- Memoization is per-render-check, not free: only adds value when the child
  subtree is expensive and would otherwise re-render pointlessly.
- In lists, keep items memoized and pass scalar props + stable callbacks;
  never pass inline object literals (`{...}`) for memoized rows.

## Context Value Pitfalls

A `Context.Provider` value object created inline changes every render and
re-renders every consumer. Memoize it:

```tsx
const value = useMemo(() => ({ theme, onToggleTheme }), [theme, onToggleTheme])
return <ThemeContext value={value}>{children}</ThemeContext>
```

## Code Splitting & Lazy Loading

Split large routes/components so the initial bundle stays small.

```tsx
import { lazy, Suspense } from 'react'

const Editor = lazy(() => import('./Editor'))

function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <Editor />
    </Suspense>
  )
}
```

- Split at **route boundaries** (most effective) or big rarely-used features
  (rich editor, charts, modals).
- `lazy` + `Suspense` for client components; Next.js uses `next/dynamic`
  (see `nextjs-performance`).
- Avoid tiny, fragmented chunks — a single `import` per route/feature, not per
  component.

## Avoiding Common Anti-Patterns

- **Inline arrow props to memoized children** defeat `memo`. Use
  `useCallback` for the handler instead.
- **Anonymous object props** (`items={{...}}`, `style={{...}}`) are new each
  render — hoist them out of the component or memoize.
- **State at the top**: if only a leaf needs state, put it in the leaf so the
  tree above doesn't re-render.
- **Context splitting**: components consuming a chatty context re-render on
  every change — split contexts (see `react-state-management`).
- **Wrong key usage** (index keys) causes full re-renders/re-mounts of list
  items — use stable ids.

## The Right Order of Optimizations

1. **Measure** with React DevTools Profiler — identify the hot component.
2. **Structural fixes first**: move state down, split components, memoize
   context values, hoist constants. (Free and usually enough.)
3. **Then** `React.memo` + `useCallback`/`useMemo` at the measured hot spots.
4. **Then** code splitting for heavy routes/features.
5. If still slow, investigate **windowing** virtual lists
   (`react-window`/`@tanstack/react-virtual`) for thousands of rows, and check
   the real DOM work (images, styles) before blaming React.

## Verification

- `npm run build` shows split chunks; initial bundle excludes lazy routes.
- React DevTools Profiler shows the memoized component no longer re-renders
  on unrelated state changes.
- `useMemo`/`useCallback` are only present where a measured or structural
  benefit exists — no blanket wrapping.
- Context provider values are memoized; state lives as low as possible.
- Inline objects/arrows aren't passed to memoized children in hot paths.
