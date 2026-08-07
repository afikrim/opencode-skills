---
name: react-testing
description: Test React components and hooks with Vitest + React Testing Library + user-event: what to test, rendering and querying, firing user interactions, testing async updates and data fetching, testing hooks with renderHook, mocking, and accessibility-driven queries. Use when the user asks how to test React components, write tests with Vitest, Testing Library, or user-event, mock fetch or a component, test hooks, or check "getByRole", "waitFor", "renderHook", "userEvent". Triggers on "react testing", "vitest", "testing library", "user-event", "test component", "test hook", "renderHook", "mock fetch", "getByRole", "waitFor".
---

# React — Testing (Vitest + Testing Library)

Component tests verify **behavior as the user experiences it**: render the
component, interact with it, assert on the DOM and state. They are not
implementation tests.

> **Related skills:** testing inside Next.js? Load `nextjs-testing` for the
> App Router specifics (mocking next/navigation, next/headers, Server Actions,
> Playwright E2E). This skill covers the React Testing Library layer.

## Stack

- **Vitest** — runner + matchers.
- **@testing-library/react** — `render`, `screen`, `waitFor`, `renderHook`.
- **@testing-library/user-event** — realistic user interactions.
- **@testing-library/jest-dom** — DOM matchers (`toBeInTheDocument`,
  `toHaveTextContent`, `toBeDisabled`).

```tsx
// Component.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Counter } from './Counter'

test('increments when the button is clicked', async () => {
  const user = userEvent.setup()
  render(<Counter />)

  const button = screen.getByRole('button', { name: /increment/i })
  await user.click(button)

  expect(screen.getByText('1')).toBeInTheDocument()
})
```

## What to Test (and What Not To)

**Test** the user-visible contract:
- Rendering given props/state: "shows the empty state when there are no items".
- Interactions: clicks, typing, keyboard, focus changes.
- Conditional UI: error/loading/success states.
- Async behavior: data appears after fetch resolves.

**Don't test** React internals:
- Don't assert on implementation details (class names, internal state shape,
  `dispatch` calls, React internals).
- Don't test third-party libraries — mock them at the boundary.
- Don't snapshot-test whole components (brittle). Keep a snapshot only for
  deliberate output stability like generated text.

## Query Priority (accessibility first)

1. **`getByRole`** — the primary choice (button, textbox, heading, dialog…).
   Mirrors screen readers and how users find things.
2. **`getByLabelText`** — form inputs, pairs with `<label htmlFor>` /
   `aria-label`.
3. **`getByPlaceholderText`**, **`getByText`**, **`getByDisplayValue`** — when
   no role/label fits.
4. **`getByTestId`** — last resort for things users can't see (needs
   `data-testid`). Never the default.

Use `name:` to disambiguate: `getByRole('button', { name: 'Save' })`.
Prefer `*ByRole` queries with `{ name: /regex/i }` over fragile exact text.

## User Interactions (user-event, not fireEvent)

```tsx
const user = userEvent.setup()
await user.click(button)
await user.type(input, 'John')      // types char by char, fires real events
await user.clear(input)
await user.selectOptions(select, 'option')
await user.hover(element)
```

- `user-event` simulates real key/pointer events; `fireEvent` is lower-level
  and often misses behavior (controlled inputs, debouncing). Default to
  `user-event`.
- Call `userEvent.setup()` per test for isolated state.

## Async Testing

```tsx
test('shows users after load', async () => {
  render(<Users />)
  expect(screen.getByText('Loading…')).toBeInTheDocument()
  await screen.findByText('Alice') // waits & retries (auto)
  // or: await waitFor(() => expect(screen.getByText('Alice')).toBeInTheDocument())
})
```

- Use `findBy*` for elements appearing after async work — it retries until the
  timeout.
- Wrap assertions that depend on settled async state in `waitFor`/`findBy`.
- Always `await` promises/user actions — otherwise you test un-flushed state.

## Testing Data Fetching

Mock the fetch boundary, not the component's internals.

```tsx
import { vi } from 'vitest'
vi.mock('../api', () => ({
  getUsers: vi.fn().mockResolvedValue([{ id: 1, name: 'Alice' }]),
}))

test('renders fetched users', async () => {
  render(<Users />)
  expect(await screen.findByText('Alice')).toBeInTheDocument()
})
```

- With TanStack Query: wrap renders in `QueryClientProvider` with a fresh
  `QueryClient` (per test) — or use `Mock Service Worker` (MSW) to intercept
  network at the HTTP layer for integration-style tests.
- Mock `window.fetch` only when your code calls it directly.

## Testing Custom Hooks (renderHook)

```tsx
import { renderHook, act } from '@testing-library/react'
import { useCounter } from './useCounter'

test('increments', () => {
  const { result } = renderHook(() => useCounter(0))
  expect(result.current.count).toBe(0)

  act(() => result.current.increment())
  expect(result.current.count).toBe(1)
})
```

- Wrap with a provider if the hook consumes context (`wrapper` option).
- Use `act` around state changes triggered from the test.
- Test a hook through a component when the behavior is UI-coupled; `renderHook`
  is best for logic-only hooks.

## Mocking Components & Utilities

```tsx
vi.mock('../heavy-chart', () => ({
  Chart: () => <div data-testid="mock-chart" />,
}))
```

- Mock only what's irrelevant to the test (heavy libs, analytics, wrappers).
- Assert against the **real behavior** of the component under test.
- `vi.fn()` for spies: `const onClose = vi.fn()` then
  `expect(onClose).toHaveBeenCalledWith(id)`.

## Test Organization

- **Co-locate** `Component.test.tsx` next to the component.
- **Arrange–Act–Assert**: set up, interact, assert. Keep each test focused on
  one behavior.
- One behavior per test; readable test names as sentences.
- Reuse helpers (renderers, providers) via `setup()` functions or a
  `test-utils.tsx` re-exporting Testing Library with a configured render that
  wraps providers (QueryClient, Router, Theme).

## Configuration Notes

- `jsdom` (or `happy-dom`) environment for DOM APIs.
- Enable `@testing-library/jest-dom/vitest` once in a setup file.
- `user-event` is async — await it; configure `environment: 'jsdom'` in
  `vite.config.ts` for Vitest.

## Verification

- `npm test` (or `npx vitest run`) passes.
- Queries are role/label-based; no `getByTestId`-first patterns.
- Interactions use `user-event` and are awaited.
- Async assertions use `findBy*`/`waitFor` and are awaited.
- Fetch/server data is mocked at the boundary; no real network in unit tests.
- Tests assert user-visible behavior, not implementation details.
