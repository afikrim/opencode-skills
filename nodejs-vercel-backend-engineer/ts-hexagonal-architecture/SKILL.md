---
name: ts-hexagonal-architecture
description: Structure TypeScript applications on Vercel using hexagonal (ports & adapters) architecture with Hono as the HTTP framework, a single api/[[route]].ts catch-all Vercel Function, Drizzle ORM for data access, and thin handlers/adapters designed so they need no tests. Uses dto+mapper patterns so no layer leaks entity models into external dependencies or presentation. Use when the user asks to scaffold a TypeScript API on Vercel, organize code into core/ports/service/adapters/handlers layers, define domain entities and ports, implement adapters (postgres, redis, queue, etc.), build Hono routes, or wire up the app with zod-env config. Triggers on "hexagonal architecture", "ports and adapters", "scaffold a TypeScript API", "Hono on Vercel", "api/[[route]].ts", "clean architecture in TypeScript".
---

# Hexagonal Architecture (TypeScript on Vercel)

Apply this layout whenever scaffolding or extending a TypeScript application
deployed to Vercel. The entrypoint is a single Vercel Function that mounts a
Hono app; everything below it is the same hexagonal shape as any other backend.

## Directory Layout

```text
<project>/
├── api/
│   └── [[route]].ts            # single catch-all Vercel Function: mounts the Hono app
├── src/
│   ├── core/
│   │   ├── entity/<entity>.ts  # domain entities, value types, enums
│   │   └── ports/<port>.ts     # interfaces (contracts), grouped by use
│   ├── service/<service>.ts    # service layer, implements use cases
│   ├── adapters/
│   │   └── <adapter>/          # postgres, redis, queue, mock, ...
│   │       ├── <adapter>.ts    # thin impl, calls dto mappers
│   │       └── dto/
│   │           ├── <dto-model>.ts # adapter's own model
│   │           └── mapper.ts   # pure entity<->dto mappers
│   ├── handlers/
│   │   ├── routes.ts           # Hono root file: basePath + route registration
│   │   ├── <handler>.ts        # one file per endpoint/resource
│   │   └── dto/
│   │       ├── <dto-model>.ts  # request/response models
│   │       └── mapper.ts       # pure dto<->service/entity mappers
│   └── config/config.ts        # app config validated via zod
├── drizzle/
│   ├── schema.ts               # Drizzle table definitions
│   └── <migration>.sql         # generated migrations
├── drizzle.config.ts           # drizzle-kit config (dialect, schema, out)
├── vitest.config.ts
├── tsconfig.json
└── package.json
```

## The Vercel Entrypoint: `api/[[route]].ts`

Vercel treats every file under `api/` as a Function; a catch-all
`[[route]]` file captures **every path** under that prefix and hands it to one
Hono app. This is the only place the app meets Vercel.

```ts
// api/[[route]].ts
import { handle } from 'hono/vercel'
import { app } from '../src/handlers/routes'

export const config = {
  runtime: 'edge', // or 'nodejs' — see Runtime Notes
}

export default handle(app)
```

- `handle(app)` from `hono/vercel` adapts the Hono app to Vercel's Function
  signature. Import it from `hono/vercel`, not `hono/node-server` (that one is
  for self-hosted Node servers).
- The default export is the only thing Vercel calls. No HTTP server is ever
  started — Vercel manages invocation, scaling, and lifecycle.
- Keep this file **empty of logic**: it imports a pre-wired `app` and exports
  the handler. All route wiring lives in `src/handlers/routes.ts`.

### Runtime Notes

- `runtime: 'edge'` runs on the Vercel Edge Runtime: fast cold starts, no
  Node.js APIs. Works if your adapters use only Web-standard APIs (fetch,
  neon-http / http drivers). Drizzle's `neon-http` and `postgres` HTTP drivers
  are edge-compatible.
- `runtime: 'nodejs'` runs on the Node.js runtime and supports full Node
  APIs (node-postgres pools, fs, etc.). Choose nodejs when an adapter needs a
  TCP connection, native module, or a Node-only library.
- Whatever you pick, run locally with `vercel dev` (not a custom dev server) so
  the routing match mirrors production.
- Environment variables come from Vercel's environment (`.env` is loaded
  locally by `vercel dev`). No `dotenv` call needed in the function.

## Layer Responsibilities

### 1. `api/[[route]].ts`

- Import the wired Hono `app`, adapt with `handle`, export it.
- **Never** build adapters/services/handlers here. Wiring lives in a bootstrap
  module (`src/handlers/routes.ts` or `src/app.ts`) so tests can build the same
  graph without importing Vercel glue.

### 2. `src/core/entity/<entity>.ts`

- Pure domain types: classes/objects, value objects, enums, constants.
- No database, HTTP, or framework imports. No `sql`, `Context`, or Hono types.
- Domain logic (business rules that apply everywhere) lives here.

### 3. `src/core/ports/<port>.ts`

Interfaces are the contracts, owned by the core. Two kinds, both declared here:

- **Service dependency ports**: interfaces the service layer requires from its
  dependencies (e.g. `UserRepository`, `CacheRepository`, `Publisher`).
- **Handler dependency ports**: interfaces the handler layer requires from
  services (e.g. `UserService`, `OrderService`).

Naming: `Name + role`, e.g. `UserRepository`, `CacheStore`, `MessagePublisher`.

```ts
// src/core/ports/user-repository.ts
import type { User } from '../entity/user'

export interface UserRepository {
  findById(id: string): Promise<User | null>
  save(user: User): Promise<void>
}
```

### 4. `src/service/<service>.ts`

- Implements the use cases the handlers need.
- Depends on **ports** (interfaces), never on concrete adapters.
- Receives its dependencies via constructor injection:
  `export class UserService implements UserServicePort { constructor(private readonly repo: UserRepository) {} }`.
- Implements the **handler dependency ports** declared in `src/core/ports/`.
- Keeps orchestration here: validation of domain rules, transaction boundaries,
  calling repository/cache/publisher ports.

### 5. `src/adapters/<adapter>/...`

Adapters are **thin glue** — designed so they never need testing.

- One folder per adapter type (postgres, redis, queue, mock, ...).
- Implements the service dependency ports for a concrete technology:
  `src/adapters/postgres/user-repository.ts`, `src/adapters/redis/cache-store.ts`.
- Holds the concrete Drizzle `db`, Redis client, queue producer, etc.
- Constructor takes its own deps:
  `export class PostgresUserRepository implements UserRepository { constructor(private readonly db: DB) {} }`.

**Adapters own their own model — never the entity directly.** Each adapter has
a `dto/` folder:

- `src/adapters/<adapter>/dto/<dto-model>.ts` — the adapter's data model (row
  shape, cache value shape, queue payload shape).
- `src/adapters/<adapter>/dto/mapper.ts` — the pure entity↔DTO mappers
  (`fromEntity(u: User): UserRow`, `toEntity(d: UserRow): User`).
- The port interface the adapter implements **still uses entity types**. Only
  the adapter implementation maps entity ↔ DTO, and the mapping is called
  inside the adapter methods.

```ts
// dto/user-row.ts — adapter's own model
export interface UserRow {
  id: string
  email: string
}

// dto/mapper.ts — pure entity↔dto mappers
export function fromEntity(u: User): UserRow {
  return { id: u.id, email: u.email }
}

export function toEntity(d: UserRow): User {
  if (!d.id) throw new Error('user row: empty id')
  return { id: d.id, email: d.email }
}
```

Thin-adapter pattern — the adapter method is only:

1. map entity → DTO (before the driver call);
2. driver call (`db.select()`, `client.get`, `publish`, ...);
3. extract/scan the DTO;
4. map DTO → entity (after the driver call);
5. error pass-through (row-not-found → `null`/sentinel).

```ts
// postgres/user-repository.ts — thin: entity↔DTO mapped inside the adapter
export class PostgresUserRepository implements UserRepository {
  constructor(private readonly db: DB) {}

  async findById(id: string): Promise<User | null> {
    const rows = await this.db.select().from(usersTable).where(eq(usersTable.id, id)).limit(1)
    if (rows.length === 0) return null
    return toEntity(rows[0]) // entity comes out of the adapter
  }

  async save(user: User): Promise<void> {
    const d = fromEntity(user) // entity goes in, DTO hits the driver
    await this.db.insert(usersTable).values(d).onConflictDoUpdate({ target: usersTable.id, set: d })
  }
}
```

- DTOs are plain interfaces; the entity↔DTO mappers are pure functions — both
  are unit-test targets.
- Zero business rules in adapters — anything that makes a decision goes to
  entity/service.
- Keep adapter methods ≤ ~5 lines; longer means logic is sneaking in.

### 6. `src/handlers/...`

The presentation layer, backed by Hono. Two parts:

- `src/handlers/routes.ts` — the root file. Creates the Hono app, sets
  `basePath('/api')`, registers routes and middleware, and exports the wired
  `app`. This is what `api/[[route]].ts` imports. It is also the composition
  root: build adapters → services → handlers here (or delegate to a
  `src/app.ts` bootstrap that tests can reuse).
- `src/handlers/<handler>.ts` — one file per endpoint/resource
  (`user.ts`, `auth.ts`), each exporting a Hono sub-app or route group.

```ts
// src/handlers/routes.ts
import { Hono } from 'hono'
import { logger } from 'hono/logger'
import { createUserRoutes } from './user'
import { PostgresUserRepository } from '../adapters/postgres/user-repository'
import { UserService } from '../service/user-service'
import { db } from '../adapters/postgres/db'

export const app = new Hono().basePath('/api')

const userRepo = new PostgresUserRepository(db)
const userService = new UserService(userRepo)

app.use('*', logger())
app.route('/users', createUserRoutes(userService))

export type App = typeof app
```

Per-endpoint handler rules:

- Depends on **handler dependency ports** (the service interfaces), injected via
  constructor/function args.
- Translates Hono's request → service call → Hono response. No database or
  adapter access here.

```ts
// src/handlers/user.ts
import { Hono } from 'hono'
import type { UserService } from '../core/ports/user-service'
import * as dto from './dto/user-dto'

export function createUserRoutes(svc: UserService) {
  return new Hono()
    .get('/', async (c) => {
      const users = await svc.list()
      return c.json({ users: users.map(dto.toUserResponse) }) // never encode an entity
    })
    .post('/', async (c) => {
      const body = await c.req.json<dto.RegisterRequest>()
      const user = await svc.register(dto.toRegisterRequest(body))
      return c.json(dto.toUserResponse(user), 201)
    })
}
```

**Handlers own their own model — never the entity directly.** Each handler has
a `dto/` folder plus pure mappers:

- `src/handlers/dto/<dto-model>.ts` — request/response models for the HTTP
  layer (JSON shapes).
- `src/handlers/dto/mapper.ts` — pure mappers between the DTOs and the
  service/entity types.
- The handler dependency port still uses service/entity types. The handler
  binds a DTO, maps to a service request, calls the service, and maps the
  result to a response DTO.

```ts
// dto/user-dto.ts — presentation's own model
export interface RegisterRequest { email: string; password: string }
export interface UserResponse { id: string; email: string }

// dto/mapper.ts — pure mappers: dto ↔ service
export function toRegisterRequest(body: RegisterRequest): service.RegisterRequest {
  return { email: body.email, password: body.password }
}

export function toUserResponse(u: User): UserResponse {
  return { id: u.id, email: u.email }
}
```

Handlers are **thin glue** — designed so they never need testing. The handler
body is only:

1. parse Hono's request body/params/query into a request DTO;
2. map request DTO → service request;
3. call one service method;
4. map the result → response DTO;
5. return the Hono response.

- All validation, DTO/response mapping, and auth extraction with real logic
  goes into **pure functions** (unit-test targets) — never inline in the
  handler. Hono's `zValidator` middleware is the idiomatic way to do schema
  validation at the edge; keep the schema/transform in `dto/`.
- Zero business rules in handlers; they decide nothing, they only translate.
- Keep handler bodies ~10 lines; longer means logic is sneaking in.

### 7. `src/config/config.ts`

Validate config with `zod` — never trust raw `process.env`:

```ts
import { z } from 'zod'

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  DATABASE_URL: z.string().url(),
  DATABASE_AUTH_TOKEN: z.string().optional(),
  REDIS_URL: z.string().url().optional(),
})

const parsed = envSchema.safeParse(process.env)
if (!parsed.success) {
  throw new Error(`invalid environment: ${parsed.error.issues.map((i) => i.path.join('.')).join(', ')}`)
}

export const config = parsed.data
```

Rules for config:

- One `z.object` schema describing everything the app reads from env.
- `z.enum`, `z.string().url()`, `.optional()`, `.default()` encode the contract
  the way `,required` / `envDefault` did in the Go skill.
- Throw with a descriptive message on startup if required vars are missing —
  fail fast in `api/[[route]].ts` import time.
- Never destructure `process.env` ad-hoc inside services or adapters; read only
  from the validated `config`.

## Wiring

The composition root is `src/handlers/routes.ts` (imported by the catch-all
function). Build bottom-up:

1. `config` → 2. adapters (`db`, redis, queue) → 3. services → 4. handlers/routes.

For tests, keep the same composition behind a function so both `api/[[route]].ts`
and `test/` can build it:

```ts
// src/app.ts
export function createApp(overrides?: { db?: DB }): App {
  const db = overrides?.db ?? defaultDb
  const userRepo = new PostgresUserRepository(db)
  const userService = new UserService(userRepo)
  return new Hono().basePath('/api').route('/users', createUserRoutes(userService))
}
```

`api/[[route]].ts` then only does: `export default handle(createApp())`.

## Testing Strategy

This layout is designed so the **only tested layers are pure functions
(unit) and the business logic (functional)**. Handlers and adapters are thin
glue and are not test targets.

- **Unit tests** — the extracted pure functions: entity↔DTO mappers
  (`adapters/<adapter>/dto/mapper.ts`, `handlers/dto/mapper.ts`), transformers,
  helpers, and zod schemas.
- **Functional tests** — the business logic implementation (`src/service/`)
  with ports mocked (`vi.fn()`).
- **Integration tests** — real wiring handler → service → adapter with mocked
  external boundaries (in-memory SQLite for Drizzle, WireMock for external
  HTTP); asserts full-flow output against golden files.
- Handlers and adapters themselves get no dedicated tests — their logic lives
  in the pure functions, their requirements live in the service, and their
  driver contract lives in integration tests.

## Dependency Direction

```text
api/[[route]].ts → src/app.ts → handlers → ports (handler deps) → service
service → ports (service deps) → adapters
core → entity, ports (no outward deps)
```

- Dependencies point **inward**. Core knows nothing about Hono, Vercel, or
  Drizzle.
- Every concrete dependency crosses the boundary only through its port
  interface.
- Swap implementations (postgres ↔ mock, real queue ↔ in-memory) without
  touching service, handlers, or core.

## Naming Conventions

- Ports: `UserRepository`, `CacheStore`, `MessagePublisher` (file
  `ports/user-repository.ts`, class/interface names PascalCase).
- Service impls: `UserService` implementing `UserService` port.
- Adapters: `postgres/PostgresUserRepository`, `redis/RedisCacheStore`,
  `queue/Publisher`.
- Handlers: one file per resource (`handlers/user.ts`) + `handlers/routes.ts`
  as the root/route-mapping file.
- DTOs: `dto/UserRow`, `dto/RegisterRequest`, `dto/UserResponse` — one `dto/`
  folder per adapter and per handler. Models live in `<dto-model>.ts`, the pure
  mappers (`fromEntity`, `toEntity`, `toRegisterRequest`, `toUserResponse`)
  live in `dto/mapper.ts`.
- Files: kebab-case for files, PascalCase for classes/types, camelCase for
  functions/instances.

## Verification

- `npm run build` (tsc) must pass; `tsc --noEmit` is a strict type check.
- Confirm no Drizzle, Hono, or Redis types leak into `core/`.
- Confirm services receive ports, not adapters; handlers receive ports, not
  service concrete types.
- Confirm adapters and handlers are thin: no business rules, no inline mapping
  logic, methods within the size limits above.
- Confirm adapters never touch `entity` types directly — only via
  `adapters/<adapter>/dto/` mappers. Port interfaces keep using entity.
- Confirm handlers never encode/accept `entity` types directly — only via
  `handlers/dto/` models and `dto/mapper.ts`.
- Confirm `api/[[route]].ts` contains no logic — only `handle(createApp())`.
- Confirm the DTOs and mappers are pure and unit-testable (no driver/Hono types
  in their signatures).
