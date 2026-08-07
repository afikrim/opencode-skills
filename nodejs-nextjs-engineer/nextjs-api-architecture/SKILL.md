---
name: nextjs-api-architecture
description: Structure the backend of a Next.js (App Router) app with hexagonal (ports & adapters) architecture when business logic lives in Next.js. Applies the ts-hexagonal-architecture patterns to Route Handlers, Server Actions, and RSC pages sharing one service layer, with thin route.ts handlers and dto/mapper patterns. Also decides when NOT to use this: thin BFF proxies stay simple, and non-trivial APIs with external consumers move to a separate service using ts-hexagonal-architecture. Use when the user asks how to structure API code inside Next.js, organize Route Handlers/Services/adapters, separate business logic from route.ts, or reuse one service layer across Route Handlers, Server Actions, and pages. Triggers on "nextjs api architecture", "hexagonal in nextjs", "route handler architecture", "server action service layer", "organize nextjs backend", "lib/server structure".
---

# Hexagonal Architecture for a Next.js API

Use this skill when the backend logic **lives inside Next.js** and is
non-trivial enough to warrant structure. It applies the `ts-hexagonal-architecture`
patterns (ports & adapters, thin handlers, dto+mapper) to the Next.js
environment, where **three thin entrypoints share one service layer**.

## Before you use this skill

Read `nextjs-api-decision` first. This skill assumes you've chosen to put
real business logic in Next.js (Route Handlers / Server Actions / RSC). If
your Route Handlers are just thin BFF proxies to an external API, **do not**
apply full hexagonal — see "When to keep it simple" below. If the API has
external consumers, long-running work, or non-HTTP protocols, use a separate
service with `ts-hexagonal-architecture` instead.

## The insight: one service layer, three entrypoints

Next.js lets three different "presentation" layers call the **same** service:

1. **Route Handlers** (`app/api/**/route.ts`) — public HTTP endpoints, webhooks.
2. **Server Actions** (`'use server'`) — mutations from the app's own UI.
3. **RSC pages** (`app/**/page.tsx`) — direct server-side data fetching.

Business logic is written once in `service/` + `core/ports/`; each entrypoint
is a **thin** translation layer that never imports the DB or business rules
directly. This is exactly the hexagonal dependency direction: dependencies
point inward, core knows nothing about Next.js.

## Directory Layout

```text
app/
├── api/
│   └── users/
│       └── route.ts           # Route Handler = thin presentation for HTTP
├── server/                     # the hexagonal core (colocated, not "internal/")
│   ├── core/
│   │   ├── entity/user.ts      # domain entities, value types, enums
│   │   └── ports/user-repo.ts  # interfaces (contracts), grouped by use
│   ├── service/
│   │   └── user-service.ts     # business logic, depends on ports
│   ├── adapters/
│   │   ├── db/user-repo.ts     # Drizzle implementation of a port
│   │   └── external/payment.ts # third-party API adapter
│   ├── handlers/               # presentational dto + mappers, shared by entrypoints
│   │   ├── user-dto.ts         # request/response models (JSON shapes)
│   │   └── user-mapper.ts      # pure dto <-> service/entity mappers
│   └── config/config.ts        # zod-validated env
├── actions.ts                  # 'use server' thin wrappers over the service
└── layout.tsx / page.tsx
```

Naming note: `server/` is the conventional Next.js home for non-component,
server-only code (also nice: `next.config.js` `serverExternalPackages`
boundaries are clearer). Some teams prefer `lib/server/`. Pick one and be
consistent. **Never** put `core/`/`service/` inside `app/` (except entrypoints)
to keep them out of the routing tree.

## Layer Responsibilities

### 1. `app/api/**/route.ts` — Route Handler (thin presentation)

Exactly like `handlers/<handler>` in the Go/TS hexagonal skills: parse the
request, validate, map DTO → service call, map result → response. No DB, no
business rules.

```ts
// app/api/users/route.ts
import { NextResponse } from 'next/server'
import { createUserService } from '@/server/service/user-service'
import { toUserResponse, toCreateUserRequest } from '@/server/handlers/user-mapper'
import { z } from 'zod'

const bodySchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
})

export async function GET() {
  const users = await createUserService().list()
  return NextResponse.json({ users: users.map(toUserResponse) })
}

export async function POST(request: Request) {
  const body = bodySchema.safeParse(await request.json())
  if (!body.success) {
    return NextResponse.json({ error: 'invalid input' }, { status: 400 })
  }
  const user = await createUserService().create(toCreateUserRequest(body.data))
  return NextResponse.json(toUserResponse(user), { status: 201 })
}
```

- **Never** call the adapter/DB here. Use the service.
- Keep the handler body ≤ ~10 lines; longer means logic is sneaking in.
- Route Handlers are **not test targets** — their logic lives in pure mappers
  (unit tests) and the service (functional tests).

### 2. `server/core/` — entity + ports

Identical to the generic hexagonal skill:

- `entity/` — pure domain types; no `next/*`, Hono, or DB imports.
- `ports/` — interfaces the service depends on (`UserRepository`,
  `CacheStore`, `MessagePublisher`), typed with entity types.

```ts
// server/core/ports/user-repo.ts
import type { User } from '../entity/user'

export interface UserRepository {
  findById(id: string): Promise<User | null>
  create(user: User): Promise<User>
}
```

### 3. `server/service/` — business logic

Implements use cases, depends **only on ports** (constructor injection), never
on concrete adapters or Next.js APIs. This is the functional-test target.

```ts
// server/service/user-service.ts
import type { UserRepository } from '../core/ports/user-repo'

export class UserService {
  constructor(private readonly repo: UserRepository) {}
  async list() {
    return this.repo.findAll()
  }
  async create(input: CreateUserInput) {
    // validation of domain rules, orchestration — no DB here
    return this.repo.create(toEntity(input))
  }
}

// simple factory so entrypoints stay thin (no manual DI wiring)
let _svc: UserService | null = null
export function createUserService(repo: UserRepository = createUserRepo()) {
  _svc ??= new UserService(repo)
  return _svc
}
```

- Constructor injection + a tiny `createUserService()` factory keeps every
  entrypoint one-liner. Use a real DI container only when the graph gets big.
- Business rules and orchestration live here — never in `route.ts`, Server
  Actions, or components.

### 4. `server/adapters/` — thin glue

Same thin-adapter pattern as the generic skill: adapter method = map entity →
DTO → driver call → DTO → entity, ≤ ~5 lines, errors passed through. Owns its
own model via `dto/` + `mapper.ts` so no entity leaks into the driver.

```ts
// server/adapters/db/user-repo.ts
import { eq } from 'drizzle-orm'
import { usersTable } from '@/drizzle/schema'
import type { UserRepository } from '../../core/ports/user-repo'
import type { User } from '../../core/entity/user'
import { toRow, toEntity } from './mapper'

export class DrizzleUserRepository implements UserRepository {
  constructor(private readonly db: DB) {}
  async findById(id: string): Promise<User | null> {
    const rows = await this.db.select().from(usersTable).where(eq(usersTable.id, id)).limit(1)
    return rows.length ? toEntity(rows[0]) : null
  }
  async create(user: User): Promise<User> {
    const row = toRow(user)
    await this.db.insert(usersTable).values(row)
    return toEntity(row)
  }
}
```

- DB access goes through Drizzle (see `ts-hexagonal-architecture`); adapters
  are swappable (db ↔ in-memory/mock) without touching the service.
- Adapters are not test targets; their pure mappers are unit tests, the
  adapter/driver contract is integration-tested (see `ts-integration-test`).

### 5. `server/handlers/` — shared presentational DTOs + mappers

The JSON shapes and pure conversions, shared by Route Handlers, Server
Actions, and RSC pages so the response model is defined once.

```ts
// server/handlers/user-dto.ts
export interface UserResponse { id: string; email: string }
export interface CreateUserInput { email: string; password: string }

// server/handlers/user-mapper.ts
export function toUserResponse(u: User): UserResponse {
  return { id: u.id, email: u.email } // never expose the entity directly
}
```

### 6. `app/actions.ts` — Server Actions (thin wrappers)

Server Actions are entrypoints for UI mutations, so they stay thin too: parse
the form/input, call the service, revalidate, return state.

```ts
'use server'
import { revalidatePath } from 'next/cache'
import { createUserService } from '@/server/service/user-service'

export async function createUser(_prev: unknown, formData: FormData) {
  const svc = createUserService()
  await svc.create({
    email: String(formData.get('email')),
    password: String(formData.get('password')),
  })
  revalidatePath('/users')
  return { ok: true }
}
```

- Form validation via zod at the action boundary, business rules stay in the
  service.
- `revalidatePath`/`revalidateTag` after mutations — the caching concern lives
  at the entrypoint, not in business logic.

### 7. RSC pages — read path

Pages fetch data **directly from the service** (not through your own Route
Handlers — see `nextjs-api-decision`):

```tsx
// app/users/page.tsx
import { createUserService } from '@/server/service/user-service'
import { toUserResponse } from '@/server/handlers/user-mapper'

export default async function UsersPage() {
  const users = await createUserService().list()
  return (
    <ul>
      {users.map((u) => (
        <li key={u.id}>{toUserResponse(u).email}</li>
      ))}
    </ul>
  )
}
```

## Dependency Direction

```text
app/api/**/route.ts ─┐
app/actions.ts ──────┼─→ server/service → server/core/ports → server/adapters
app/**/page.tsx ─────┘
```

- Entrypoints (route.ts, actions, pages) depend only on `service/` +
  `handlers/` DTOs.
- Service depends only on ports (interfaces), never adapters or Next.js.
- Adapters implement ports; core knows nothing about Next.js, Drizzle, or HTTP.

## When to Keep It Simple (thin BFF)

If the Route Handler is just forwarding to an external API with validation,
full hexagonal is overkill — skip `service/`/`core/` and keep:

```ts
// app/api/weather/route.ts — thin proxy, no hexagonal needed
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const res = await fetch(`${process.env.WEATHER_API}?q=${searchParams.get('q')}`, {
    headers: { Authorization: `Bearer ${process.env.WEATHER_API_KEY}` },
  })
  return new Response(res.body, { status: res.status })
}
```

Use the decision tree in `nextjs-api-decision`:
- Thin proxy / single webhook / BFF → keep it simple, no hexagonal.
- Real business logic shared by UI + HTTP + actions → this skill.
- External consumers / long-running / WebSocket → separate service with
  `ts-hexagonal-architecture` (this skill's layout is the "lite" version).

## Testing Strategy

- **Unit tests** — pure mappers (`server/handlers/user-mapper.ts`), entity
  logic, zod schemas. (See `nextjs-testing` + `ts-unit-test`.)
- **Functional tests** — `server/service/*` with ports mocked (`vi.fn()`).
  (See `ts-functional-test`.)
- **Integration tests** — route.ts → service → adapter with Drizzle against
  in-memory SQLite + WireMock for external APIs, golden files for responses.
  (See `ts-integration-test`.)
- Route Handlers / Server Actions / adapters get **no dedicated tests** — thin
  glue by design.

## Verification

- `npm run build` (tsc) passes.
- `route.ts`, `actions.ts`, and pages import only `service/` + `handlers/`
  DTOs — never `adapters/` or the DB directly.
- No `next/*` imports inside `server/core/`, `server/service/`, or adapters.
- No `process.env` reads outside `server/config/config.ts`.
- Entrypoint bodies stay thin (~≤10 lines); service holds the logic.
- Functional tests mock the ports; integration tests exercise route → service
  → adapter end-to-end.
- For thin BFF/proxy handlers, the service/core layers were skipped on purpose.
