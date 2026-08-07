---
name: react-state-management
description: Choose and apply the right state management approach in React: local useState, useReducer for complex update logic, Context for passing state deep, the reducer + context provider pattern, and when to reach for external libraries (Zustand, Redux Toolkit, Jotai) or server-state libraries (TanStack Query, SWR). Use when the user asks how to manage state in React, whether to use Context or a state library, how to structure reducers and providers, split UI state from server state, or avoid prop drilling. Triggers on "state management", "useReducer", "useContext", "context provider", "zustand", "redux toolkit", "tanstack query", "swr", "prop drilling", "lift state".
---

# React — State Management

State management is a **ladder**: start with the simplest tool that works, and
climb only when a specific pain appears.

## The Ladder

1. **`useState`** — local component state. Default for everything.
2. **`useReducer`** — complex update logic, many related state updates, or
   when you want state-update logic extracted and testable.
3. **Context** — pass data/handlers deep without prop drilling (not a state
   store by itself).
4. **Reducer + Context provider** — shared state for a subtree with structured
   updates (the "scaling up" pattern).
5. **External client-state library** (Zustand / Redux Toolkit / Jotai) — state
   shared across large parts of the app with frequent updates, devtools,
   middleware, or persistence.
6. **Server-state library** (TanStack Query / SWR) — **separate concern**:
   any data coming from an API belongs here, not in a global store.

## 1. useState (default)

- Local state owned by one component. Keep it as low as possible; lift only
  when siblings need it.

```tsx
function FeedbackForm() {
  const [isSent, setIsSent] = useState(false)
  const [message, setMessage] = useState('')
  // ...
}
```

- Keep state minimal: store what changes over time, derive the rest during
  render (filtered lists, computed totals) — see `react-architecture`.

## 2. useReducer (when updates get complex)

Choose `useReducer` when: many event handlers update state in similar ways,
updates depend on previous state in non-trivial ways, or you want to debug
"which action caused this state".

```tsx
function tasksReducer(tasks: Task[], action: TaskAction): Task[] {
  switch (action.type) {
    case 'added': return [...tasks, action.task]
    case 'changed': return tasks.map(t => (t.id === action.task.id ? action.task : t))
    case 'deleted': return tasks.filter(t => t.id !== action.id)
    default: throw new Error('Unknown action: ' + action.type)
  }
}

function TaskApp() {
  const [tasks, dispatch] = useReducer(tasksReducer, initialTasks)
  // dispatch({ type: 'added', task })
}
```

- The reducer must be **pure** — no side effects, no `Math.random`, no I/O.
  (Side-effectful actions are what `useActionState` is for, not reducers.)
- Extract the reducer to its own function so it's unit-testable.

## 3. Context (avoid prop drilling, not a store)

Context lets you pass values to a whole subtree without threading props.
It is **not** state management on its own — combine with state/state library.

```tsx
const ThemeContext = createContext<'light' | 'dark'>('light')

function App() {
  return (
    <ThemeContext value="dark">
      <Toolbar />
    </ThemeContext>
  )
}
```

- Wrap the provider's value in `useMemo` when it's an object/array created each
  render (avoids re-rendering every consumer).
- Keep contexts **coarse-grained and few**; a context changing on every
  keystroke re-renders all its consumers.
- Split state and dispatch into **two contexts** when consumers only need one
  (see reducer+context below).

## 4. Reducer + Context Provider (shared state for a subtree)

The recommended pattern for state shared within a subtree (feature, section,
app) with structured updates — no external library needed. Consolidate the
reducer, contexts, and provider in one file with custom hooks:

```tsx
// tasks-context.tsx
import { createContext, useContext, useReducer } from 'react'

const TasksContext = createContext<Task[] | null>(null)
const TasksDispatchContext = createContext<Dispatch<TaskAction> | null>(null)

export function TasksProvider({ children }: { children: React.ReactNode }) {
  const [tasks, dispatch] = useReducer(tasksReducer, initialTasks)
  return (
    <TasksContext value={tasks}>
      <TasksDispatchContext value={dispatch}>
        {children}
      </TasksDispatchContext>
    </TasksContext>
  )
}

export function useTasks() {
  const ctx = useContext(TasksContext)
  if (ctx === null) throw new Error('useTasks must be used inside <TasksProvider>')
  return ctx
}

export function useTasksDispatch() {
  const ctx = useContext(TasksDispatchContext)
  if (ctx === null) throw new Error('useTasksDispatch must be used inside <TasksProvider>')
  return ctx
}
```

- Split into **state + dispatch** contexts so components that only dispatch
  don't re-render on state change.
- Custom hooks (`useTasks`, `useTasksDispatch`) enforce usage inside the
  provider and hide context plumbing.
- Throwing in the hook when used outside the provider catches wiring mistakes.

## 5. External client-state library (Zustand / Redux Toolkit / Jotai)

Reach for these only when Context/reducer is not enough: state shared across
**large unrelated parts** of the app, **frequent high-frequency updates**, or
when you need devtools/middleware/persistence/selectors.

| Library | Style | When it shines |
|---|---|---|
| Zustand | external store + hooks, minimal | simple global state, small boilerplate |
| Redux Toolkit | redux + toolkit, structured | large apps, team conventions, middleware |
| Jotai | atom-based | granular state, per-atom subscriptions |

Rules:

- Still keep the store **as small as possible** — only app-wide, cross-cutting
  state (auth session, theme, notifications) belongs there.
- Component-local and subtree state stay in `useState`/reducer+context; don't
  dump everything into a global store.

## 6. Server state (TanStack Query / SWR) — always separate

Data that comes from an API is **server state**, not client state. Manage it
with a server-state library (`@tanstack/react-query`, `swr`) for caching,
loading/error states, retries, and revalidation. Never mirror server data into
a global client store manually.

```tsx
import { useQuery } from '@tanstack/react-query'

function Users() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.getUsers(),
  })
  if (isLoading) return <p>Loading…</p>
  if (error) return <p>Failed to load</p>
  return <UserList users={data} />
}
```

- Use `useMutation` for writes (POST/PUT/DELETE) + `invalidateQueries` to
  refetch after mutation.
- Mutations that start from forms in Next.js → Server Actions (see
  `nextjs-api-architecture`); client-side SPA data stays in React Query/SWR.

## Decision Summary

| Situation | Approach |
|---|---|
| One component's local state | `useState` |
| Complex update logic, many handlers | `useReducer` |
| Pass props deep, no state change | Context (or composition with `children`) |
| Shared subtree state, structured updates | Reducer + Context provider |
| App-wide cross-cutting state, many consumers | External store (Zustand/RTK/Jotai) |
| API data with caching/loading | TanStack Query / SWR |
| Form mutations in Next.js UI | Server Actions |

## Verification

- Local UI state uses `useState`; complex updates use `useReducer` (pure).
- Context is used for passing values, not as a de-facto global store unless
  combined with the reducer/provider pattern.
- Provider value is memoized; state and dispatch are in separate contexts.
- API data lives in a server-state library, not duplicated in a client store.
- No prop drilling through more than a couple levels without a reason.
- Custom hook context accessors throw when used outside their provider.
