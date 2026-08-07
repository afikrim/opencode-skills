---
name: nextjs-testing
description: Write tests for a Next.js (App Router) application: unit tests with Vitest, component tests with Vitest + React Testing Library (synchronous Server/Client Components), and end-to-end tests with Playwright. Covers mocking next/navigation, next/headers, and fetch; testing Server Actions; and the rule that async Server Components and full routing behavior are covered by E2E, not unit tests. Use when the user asks to test Next.js components, pages, Server Actions, or App Router flows, set up Vitest/Playwright for Next.js, or add unit/component/E2E tests. Triggers on "test nextjs", "next.js testing", "vitest nextjs", "playwright nextjs", "test server action", "component test", "rsc test".
---

# Testing Next.js (App Router)

> **Related skills — load alongside this one:** `react-testing` covers the
> React Testing Library layer for Client Components (queries, user-event,
> async, renderHook, mocking) in depth; this skill adds the Next.js specifics
> (mocking next/navigation, next/headers, Server Actions). Use both together.

Three layers, each with the right tool:

1. **Unit tests** — pure logic (helpers, utilities, schemas) with Vitest.
2. **Component tests** — synchronous Server & Client Components with Vitest +
   React Testing Library.
3. **E2E tests** — full routing, async Server Components, and browser behavior
   with Playwright.

Key constraint from the docs: **Vitest does not support async Server
Components** and can't exercise the App Router's routing/loading/error
machinery — those are E2E territory.

## Setup

Start from the official templates, then adapt:

```bash
# Vitest + React Testing Library
npx create-next-app@latest --example with-vitest my-app

# Playwright
npx create-next-app@latest --example with-playwright my-app
```

`vitest.config.ts` (with the App Router pattern):

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['**/*.test.{ts,tsx}'],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
})
```

`vitest.setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
```

Scripts:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:unit": "vitest run src",
    "test:e2e": "playwright test"
  }
}
```

## 1. Unit Tests (pure logic)

Scope: helpers, formatters, zod schemas, pure functions, service logic. Same
rules as the `ts-unit-test` skill — no mocks, deterministic, fixed inputs.

```ts
import { describe, expect, it } from 'vitest'
import { slugify } from '@/lib/slugify'

describe('slugify', () => {
  it('lowercases and hyphenates', () => {
    expect(slugify('Hello World')).toBe('hello-world')
  })
})
```

## 2. Component Tests (Vitest + RTL)

Test **synchronous** Server Components (props in, JSX out) and Client
Components (state, events). Render with RTL and assert by role/text.

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { UserList } from './user-list' // 'use client'

describe('UserList', () => {
  it('filters users by query', async () => {
    render(<UserList users={[{ id: '1', name: 'Ada' }, { id: '2', name: 'Bob' }]} />)

    await userEvent.type(screen.getByPlaceholderText('Search'), 'Ada')

    expect(screen.getByText('Ada')).toBeInTheDocument()
    expect(screen.queryByText('Bob')).not.toBeInTheDocument()
  })
})
```

### Mocking Next.js APIs

Server Actions, navigation, and headers must be mocked at the module level:

```tsx
import { describe, expect, it, vi } from 'vitest'

// mock next/navigation used by a Client Component
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => '/dashboard',
  useSearchParams: () => new URLSearchParams(),
  redirect: vi.fn(),
}))

// mock next/headers (only reachable server-side)
vi.mock('next/headers', () => ({
  cookies: async () => ({ get: () => undefined }),
  headers: async () => new Headers(),
}))
```

Testing a Server Action directly (it's just a function — call it, assert the
result, mock its I/O):

```ts
import { describe, expect, it, vi } from 'vitest'
import { register } from '@/app/actions'

vi.mock('@/lib/db', () => ({ insert: vi.fn().mockResolvedValue(undefined) }))
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }))

describe('register action', () => {
  it('rejects invalid input without touching the db', async () => {
    const fd = new FormData()
    fd.set('email', 'not-an-email')
    fd.set('password', 'x')

    const res = await register({}, fd)
    expect(res.error).toBeDefined()
  })

  it('saves valid input and revalidates', async () => {
    const fd = new FormData()
    fd.set('email', 'a@b.com')
    fd.set('password', 'secret123')

    const res = await register({}, fd)
    expect(res.ok).toBe(true)
  })
})
```

Rules:

- Mock at module boundaries (`next/*`, db client, fetch), never the logic under
  test.
- **Do not attempt async Server Components in Vitest** — they aren't supported.
  Move them to Playwright.
- Global `fetch` (RSC data fetching) can be stubbed with
  `vi.stubGlobal('fetch', ...)` when testing a component that fetches.
- Use `useActionState`/`useFormStatus`-aware renders by wrapping forms in
  `render` normally — RTL works with form actions.

## 3. E2E Tests (Playwright)

E2E covers what unit/component can't: real routing, navigation, async Server
Components, server-rendered data, and the full App Router pipeline.

```ts
// e2e/flow.spec.ts
import { test, expect } from '@playwright/test'

test('registers a user and lands on dashboard', async ({ page }) => {
  await page.goto('/register')
  await page.fill('[name="email"]', 'a@b.com')
  await page.fill('[name="password"]', 'secret123')
  await page.click('button[type="submit"]')

  await expect(page).toHaveURL('/dashboard')
  await expect(page.locator('h1')).toContainText('Dashboard')
})
```

`playwright.config.ts` — auto-start the dev server:

```ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  webServer: {
    command: 'npm run build && npm run start', // or `next dev`
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
  use: { baseURL: 'http://localhost:3000' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
```

Rules:

- One E2E test per user-facing flow (register, login, checkout, navigation),
  not per function.
- Use a clean/seed DB state per run; assert user-visible outcomes (URL, text,
  data).
- Prefer `next build && next start` in CI over `next dev` for production-like
  behavior, or use the seed with a test DB.
- Keep critical paths in E2E; leave detail/edge cases to unit/component tests.

## Layer Mapping (aligns with other skills)

| Layer | Tool | Scope |
|---|---|---|
| Pure logic / schemas | Vitest (unit) | helpers, mappers, validators |
| Server Actions | Vitest (unit-style) | input validation, orchestration, mocked I/O |
| Sync Server/Client Components | Vitest + RTL | render, props, events, state |
| Async RSC, routing, loading/error, full flows | Playwright | E2E |

## Verification

- `npm run test:unit` passes (Vitest).
- `npm run test:e2e` passes against a running server (Playwright).
- No async Server Component is unit-tested in Vitest.
- `next/navigation`, `next/headers`, and `next/cache` usages are mocked in
  component/action tests.
- E2E exercises the real routing/loading boundaries (i.e. not everything is
  stubbed).
