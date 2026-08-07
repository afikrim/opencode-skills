---
name: react-architecture
description: Structure React applications with idiomatic, React-recommended patterns: component hierarchy (Thinking in React), pure components and hooks, the Rules of Hooks, component composition, lifting state, and keeping components small and focused. Use when the user asks how to organize React components, split a component, decide props vs state, follow React best practices, apply the Rules of Hooks, or fix purity issues. Triggers on "react architecture", "component hierarchy", "rules of hooks", "pure components", "component composition", "thinking in react", "lift state up", "split component".
---

# React — Component Architecture & Idioms

Follow React's canonical rules and patterns when building components. These
apply to any React codebase (plain React, Vite SPA, or inside Next.js).

> **Related skills:** running inside Next.js? Load `nextjs-architecture` for
> the server/client boundary and RSC rules — this skill covers the React layer,
> that one covers the Next.js layer.

## The Core Rules (from React docs)

1. **Components and hooks must be pure.** Same props → same output. React may
   render a component multiple times; it must be predictable.
   - No side effects during render — effects go in `useEffect` (or event
     handlers), never in the render body.
   - Never mutate props or state. Treat them as immutable snapshots of the
     current render. New values → new state via the setter.
   - Don't mutate values after they've been used in JSX — move mutation
     before the JSX is created.
2. **React calls components and hooks** — don't call component functions
   directly from your code; render them with JSX `<Component />`. Never pass
   hooks around as regular values.
3. **Rules of Hooks**:
   - Only call Hooks at the **top level** of your React function, before any
     early returns — never in loops, conditions, or nested functions.
   - Only call Hooks **from React functions** (components or custom hooks),
     never from regular JS functions.

## Component Hierarchy (Thinking in React)

Workflow for building a data-driven UI:

1. **Break the UI into a component hierarchy** — one component per
   responsibility, mirroring the visual layout (containers, rows, cells,
   buttons).
2. **Build a static version** with props only — no state yet.
3. **Find the minimal state** — ask "does it change over time?" and "can it be
   computed from existing props/state?" Only true state gets `useState`.
   Example: the filtered list is **computed** from `filterText` + `inStockOnly`
   + `products` — do not store it.
4. **Identify where state lives** — lift it to the nearest common parent that
   needs it (or a provider).
5. **Add inverse data flow** — pass event handler props (`onFilterChange`)
   down so children can update state owned by the parent.

```tsx
function FilterableProductTable({ products }: { products: Product[] }) {
  const [filterText, setFilterText] = useState('')
  const [inStockOnly, setInStockOnly] = useState(false)
  const visibleProducts = products.filter(p =>
    p.name.toLowerCase().includes(filterText.toLowerCase()) &&
    (!inStockOnly || p.stocked)
  )
  return (
    <>
      <SearchBar filterText={filterText} inStockOnly={inStockOnly}
        onFilterTextChange={setFilterText} onInStockOnlyChange={setInStockOnly} />
      <ProductTable products={visibleProducts} />
    </>
  )
}
```

## Component Design Rules

- **One component = one job.** If a component does two things (fetch + render,
  form state + layout), split it.
- **Props are the API.** Components communicate via props, not by reaching into
  other components' internals.
- **Small, focused components.** A component that's hard to read in a screen is
  a candidate to split.
- **Composition over configuration.** Prefer composing children over many
  boolean/flag props. Pass `children` (or render props / slots) instead of
  building a component that knows about every variant.

```tsx
function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  )
}
```

- **Keys**: use stable unique keys in lists (`key={item.id}`), never the index
  for reorderable lists.
- **State placement**: keep state as low as needed; lift only when multiple
  components need to read or write it. Avoid prop drilling with more than a
  couple of levels — use composition (`children`) or Context (see
  `react-state-management`).

## File Organization

```text
src/
├── components/          # reusable, presentational components
│   ├── ui/              # buttons, inputs, cards (dumb, no data-fetch)
│   └── <feature>/       # feature components
├── features/            # feature-scoped folders (page + its components/hooks)
├── hooks/               # shared custom hooks
├── lib/                 # pure utilities, api clients
├── state/               # context providers / stores (see react-state-management)
├── types/               # shared types
├── App.tsx              # composition root
└── main.tsx
```

- **Co-locate**: put a component's test, story, and CSS next to it.
- **Feature folders**: a page/feature owns its components, hooks, and logic in
  one folder; share only what must be shared.

## Custom Hooks

Extract repeated logic (subscriptions, form handling, data loading) into
custom hooks — they compose and keep components clean.

```ts
// hooks/use-online-status.ts
export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(true)
  useEffect(() => {
    const update = () => setIsOnline(navigator.onLine)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => {
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
    }
  }, [])
  return isOnline
}
```

- Name hooks `useX`; only call other hooks inside them.
- A custom hook's state/effects are **independent per usage** — each call gets
  its own instance.
- If a hook returns handlers or derived data tied to state, it usually belongs
  with that component's feature rather than a "shared" folder.

## Effects & Data Fetching

- **Effects are for synchronization with external systems** (subscriptions,
  timers, network). Not for "running after render" computations.
- Keep effects scoped: every effect has the right dependency array; clean up
  subscriptions/timers in the returned cleanup function.
- Prefer **event handlers / mutations for data changes**; effects for reading
  & synchronizing. Use a data-fetching library (`swr`, TanStack Query) for
  server state instead of hand-rolled `useEffect` fetching.
- If you don't need an effect, don't write one — derive values directly during
  render.

## Verification

- `npx tsc --noEmit` (or `npm run lint` + `npm run build`) passes.
- No hooks called in loops/conditions; hooks at top level before early
  returns.
- No side effects in the render body; mutations of props/state absent.
- State is minimal: nothing storeable-as-derived is in `useState`.
- Components are small and single-purpose; lists have stable keys.
- Shared/duplicated logic is extracted into custom hooks or utilities.
