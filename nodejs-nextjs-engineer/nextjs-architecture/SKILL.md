---
name: nextjs-architecture
description: Implement Next.js (App Router) applications optimally: server-first architecture with React Server Components, correct Client/Server Component boundaries, data fetching patterns (direct in RSC, not through Route Handlers), caching and revalidation strategies, Server Actions for mutations, and route grouping conventions. Use when the user asks to scaffold or structure a Next.js app, decide server vs client components, fetch data in a page, handle mutations/forms, set up caching or ISR, or optimize a Next.js codebase. Triggers on "next.js", "app router", "react server components", "rsc", "server actions", "data fetching in nextjs", "caching", "isr", "revalidation".
---

# Next.js (App Router) — Optimal Implementation

Apply these principles whenever building or extending a Next.js application
(App Router). The default mental model: **server-first**. Do as much as
possible on the server, and add client interactivity only where required.

> **Related skills — load alongside this one:**
> - Client/UI components live in Next.js too — load `react-architecture` for
>   component structure, Rules of Hooks, and purity.
> - `react-state-management` for client state (useState/Context/store) and
>   server state via TanStack Query/SWR in client components.
> - `react-performance` for memoization and re-render avoidance in Client
>   Components (note: use `next/dynamic` instead of `React.lazy`).
> - This skill covers the Next.js layer; those cover the React layer. Use both.

## Core Mental Model

1. **Server Components are the default.** Every component is a Server Component
   unless it needs interactivity. They run on the server, can be `async`, can
   read the DB/db client directly, and never ship their logic/imports to the
   client.
2. **Client Components are the exception.** Only add `'use client'` when the
   component needs browser APIs (state, effects, event handlers, hooks) or
   third-party interactive libraries. Keep client bundles small: prefer
   passing Server Components as children/props into client components, and
   pushing "client islands" as low in the tree as possible.
3. **Fetch data where it renders.** A Server Component fetches its own data
   directly from the data source — not through your own Route Handlers.
4. **Mutations go through Server Actions** when they start from the app's UI;
   Route Handlers are for public HTTP endpoints consumed by non-UI clients.
5. **Default to static; opt into dynamic.** Next.js static-optimizes by
   default. Use caching/revalidation explicitly rather than sprinkling
   `force-dynamic`.

## 1. Server vs Client Component Boundaries

Ask: does this component need state, effects, or event handlers? If no — keep
it a Server Component.

```tsx
// Server Component (default) — fetch directly, no 'use client'
export default async function Page() {
  const users = await getUsers() // direct DB / data-source call
  return <UserList users={users} />
}
```

```tsx
'use client' // needed: interactivity
import { useState } from 'react'

export function UserList({ users }: { users: User[] }) {
  const [filter, setFilter] = useState('')
  // ...
}
```

Rules:

- **Never fetch in a Client Component if a Server Component can do it.** Move
  the data fetch up to a parent Server Component and pass the result down.
- **Pass Server Components into Client Components as children** instead of
  importing a Server Component inside a Client Component (importing a server
  component into a client one turns it into a client component):

```tsx
'use client'
export function Card({ children }: { children: React.ReactNode }) {
  return <div className="card">{children}</div>
}

// page.tsx (Server Component) — works, RSC stays server-rendered
<Card><UserProfile /></Card>
```

- Keep `'use client'` leaves small: a button, a search box, a chart wrapper.
- Third-party libs: if they're client-only, wrap them in a small client
  component; if they support RSC (some now do), use that directly.
- Follow React's guidance on third-party RSC support for library patterns.

## 2. Data Fetching

### In Server Components (the default)

Fetch directly from the data source. Do **not** fetch through your own Route
Handlers — at build time no server is listening (build fails), and at runtime
it adds an unnecessary HTTP round-trip.

```tsx
import { db } from '@/lib/db' // direct source

export default async function Page() {
  const users = await db.query.users.findMany()
  return <UserList users={users} />
}
```

This includes fetching external APIs with secrets — do it server-side, never
expose the token to the client:

```tsx
import { cookies } from 'next/headers'

export default async function Page() {
  const token = (await cookies()).get('AUTH_TOKEN')?.value
  const res = await fetch('https://api.example.com/profile', {
    headers: { Authorization: `Bearer ${token}` },
  })
  // ...
}
```

### Client-side fetching (when it's actually needed)

Fetch client-side only for data that depends on client-only Web APIs or
frequently polled data:

- Geolocation, Storage/Audio/File APIs
- Frequently polled / real-time data

Use a data-fetching library (`swr` or TanStack Query) for caching, retries, and
revalidation rather than raw `useEffect`.

### Caching & Revalidation

- Default is static + cached (`fetch` results are cached by default in
  Server Components).
- **On-demand revalidation** is preferred over time-based ISR:
  `revalidateTag(tag, 'max')` / `revalidatePath(path)` from `next/cache` after
  data changes (e.g. after a mutation in a Server Action).
- `'use cache'` + `cacheLife('hours')` (`next/cache`) memoizes expensive data
  reads with a declarative lifetime.
- Explicitly opt into dynamic rendering only when you must:
  `export const dynamic = 'force-dynamic'` (session per request, etc.).
- Avoid overusing `revalidate` time values; prefer event-driven revalidation.

## 3. Mutations (forms, buttons, data changes)

Use **Server Actions** for mutations initiated from the app's own UI. They run
on the server, are imported directly by client components, and avoid building
API routes by hand.

```ts
'use server'
import { revalidatePath } from 'next/cache'
import { z } from 'zod'

const schema = z.object({ email: z.string().email(), password: z.string().min(8) })

export async function register(prevState: unknown, formData: FormData) {
  const parsed = schema.safeParse({
    email: formData.get('email'),
    password: formData.get('password'),
  })
  if (!parsed.success) {
    return { error: 'invalid input' } // surfaced by useActionState
  }
  await db.insert(users).values(parsed.data)
  revalidatePath('/users')
  return { ok: true }
}
```

Client consumption — use React's `useActionState` (or `useFormStatus`) to
manage pending/error state instead of manual fetch + useEffect:

```tsx
'use client'
import { useActionState } from 'react'
import { register } from '@/app/actions'

export function RegisterForm() {
  const [state, formAction, pending] = useActionState(register, {})
  return (
    <form action={formAction}>
      <input name="email" />
      <input name="password" type="password" />
      <button disabled={pending}>{pending ? 'Saving…' : 'Save'}</button>
      {state.error && <p>{state.error}</p>}
    </form>
  )
}
```

Rules:

- Mutations that only the app's UI performs → Server Actions.
- Validate inputs with a schema (`zod`) before touching the DB.
- Revalidate affected routes/tags inside the action after mutation.
- `'use server'` files are fine for shared mutations; inline `async function`
  actions also work in Server Components and `<form action={...}>`.

## 4. Directory / Route Grouping Conventions

```text
app/
├── (marketing)/              # route group: no URL segment, shared layout
│   ├── layout.tsx
│   ├── page.tsx
│   └── pricing/page.tsx
├── (app)/                    # authenticated area group
│   ├── layout.tsx            # e.g. nav + session guard
│   └── dashboard/page.tsx
├── api/                      # Route Handlers (public HTTP endpoints)
│   ├── webhook/route.ts
│   └── search/route.ts
├── actions.ts                # 'use server' mutations
├── layout.tsx                # root layout
└── page.tsx
```

Rules:

- Route groups `(name)` give a shared layout without adding a URL segment.
- `app/api/**/route.ts` = public endpoints (webhooks, third-party callbacks,
  non-UI clients). Not for the app's own pages to call.
- Keep shared server-side logic in `lib/` (`lib/db`, `lib/auth`,
  `lib/actions`); co-locate component-specific files next to the component.
- `loading.tsx`, `error.tsx`, `not-found.tsx`, `global-error.tsx` provide the
  streaming/error boundaries at each segment.

## 5. Performance & Metadata

- **Streaming**: `loading.tsx` and `Suspense` boundaries let the page render
  before slow data resolves.
- **Metadata**: export `metadata` (or `generateMetadata`) from Server
  Components — SEO without client JS. File conventions: `opengraph-image.jpg`,
  `sitemap.ts`, `robots.ts`.
- **Fonts/Images**: `next/font`, `next/image` handle optimization; never
  `<img>` a static asset you can optimize.
- Keep client bundle small; audit with `next build` output and Lighthouse.

## Verification

- `npx tsc --noEmit` passes.
- `npm run build` (or `next build`) passes; review the route/layout warnings.
- No `'use client'` in components that only render data without interactivity.
- No server component imports a client-only library directly.
- Pages fetch data directly (no self-HTTP round-trip through `/api`).
- Mutations use Server Actions; public/third-party endpoints use Route
  Handlers.
- Caching is explicit: static by default, revalidate on events, dynamic only
  when required.
- Secrets never reach the client bundle (check with a quick grep for
  `process.env` usage inside `'use client'` files).
