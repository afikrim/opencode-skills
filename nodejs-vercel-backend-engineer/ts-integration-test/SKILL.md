---
name: ts-integration-test
description: Write integration tests in TypeScript that verify the real wiring of the application layers (handler → service → adapter) while mocking external infrastructure — the database via Drizzle against an in-memory SQLite (libsql) database and external HTTP dependencies via WireMock — comparing actual results against golden files and fixtures. Use when the user asks to test components working together end-to-end, add *.test.ts files that exercise the full stack with Vitest, set up a test database or wiremock, or compare response output with golden files. Triggers on "integration test", "test the full stack", "test handler to database", "mock external api with wiremock", "golden file", "fixtures", "vitest integration".
---

# Integration Tests (TypeScript / Vitest)

An integration test verifies that the application layers **work together
through the real wiring** — `handler → service → adapter`, built exactly like
`createApp()` builds them. External infrastructure is **mocked**: the database
is an in-memory SQLite via Drizzle + libsql, and external HTTP dependencies are
mocked with **WireMock**.

The code under test runs its real logic at every layer. Only the things
outside the app boundary (production DB, third-party HTTP APIs) are fakes.

## What to Integration Test

- The full stack: Hono `app.request()` → handler → service → adapter → (test
  DB / mocked external API).
- Flows that cross adapters: a handler whose service calls both a repository
  (test DB) and a payment/notification API (WireMock).
- The real dependency wiring: that `createApp()` actually satisfies the ports
  and behaves as composed.

## Building the App Under Test

Use the same `createApp()` the Vercel function uses, but inject the test
boundaries:

```ts
// src/app.ts — production and tests share this composition root
export function createApp(overrides?: { db?: DB }): App {
  const db = overrides?.db ?? defaultDb
  const userRepo = new PostgresUserRepository(db)
  const userService = new UserService(userRepo)
  return new Hono().basePath('/api').route('/users', createUserRoutes(userService))
}
```

Integration tests import `createApp` with a test DB and drive it with Hono's
`app.request()` — no server socket needed:

```ts
import { describe, expect, it, beforeEach } from 'vitest'
import { createApp } from '../src/app'

describe('POST /api/users (integration)', () => {
  beforeEach(async () => {
    await migrateTestDb() // push schema into the in-memory SQLite
  })

  it('creates a user end-to-end', async () => {
    const app = createApp({ db: testDb })
    const res = await app.request('/api/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'a@b.com', password: 'secret' }),
    })

    expect(res.status).toBe(201)
    expect(await res.json()).toEqual({
      id: expect.any(String),
      email: 'a@b.com',
    })
  })
})
```

## Mocking the Database (Drizzle + in-memory SQLite)

Drizzle is dialect-portable: the same query API runs against Postgres
(production) and SQLite (tests). For tests, connect Drizzle to an in-memory
libsql database so the adapter queries run for real without a DB server.

Install: `npm i -D @libsql/client` (already a transitive dep of
`drizzle-orm/libsql`).

```ts
// test/setup-db.ts
import { drizzle } from 'drizzle-orm/libsql'
import { createClient } from '@libsql/client'
import { migrate } from 'drizzle-orm/libsql/migrator'
import * as schema from '../drizzle/schema'

export const testDb = drizzle({ client: createClient({ url: ':memory:' }), schema })

export async function migrateTestDb() {
  await migrate(testDb, { migrationsFolder: 'drizzle' })
}
```

Rules:

- **One in-memory DB per test file** (or per test via `beforeEach`), so tests
  never share state. `:memory:` SQLite is isolated per connection.
- Run `migrate(testDb, ...)` in `beforeAll`/`beforeEach` so the schema exists
  before queries run. Keep schema DDL idempotent.
- When a query uses a Postgres-only feature (e.g. `jsonb`, `gen_random_uuid`,
  `pgcrypto`), either keep the adapter query to portable SQL or abstract that
  difference into the adapter's `dto`/mapper. The point is to exercise the real
  adapter code path.
- Assert against what the adapter *does* (rows in the in-memory DB), not
  against SQLite internals.

## Mocking External Dependencies (WireMock)

WireMock supports two ways to define stubs:

1. **Dynamic stubs** via the `go-wiremock`/`wiremock` REST API client (best
   when a test needs stubs unique to that test, or wants to `Verify` call
   counts).
2. **Static mapping files** (best for stable, shared, conditional
   request/response contracts used across many tests).

Run a standalone WireMock server with the official Docker image, mounting the
mappings so WireMock loads them on startup:

```shell
docker run -it --rm -p 8080:8080 \
  -v ./testdata/wiremock/mappings:/home/wiremock/mappings \
  -v ./testdata/wiremock/__files:/home/wiremock/__files \
  wiremock/wiremock
```

### Static mapping files (configuration-based)

WireMock loads JSON mapping files from the `mappings/` directory. Each mapping
declares a **conditional request** (match on method, URL, headers, query
params, body) and the **response** to return. Response bodies can live inline
in the mapping or in `__files/`.

```json
// testdata/wiremock/mappings/payment.json
{
  "request": {
    "method": "POST",
    "urlPath": "/payments",
    "headers": {
      "Authorization": { "matches": "^Bearer .+$" }
    },
    "bodyPatterns": [
      { "equalToJson": { "amount": 100 }, "ignoreArrayOrder": true }
    ]
  },
  "response": {
    "status": 200,
    "headers": { "Content-Type": "application/json" },
    "bodyFileName": "payment-ok.json"
  }
}
```

```json
// testdata/wiremock/__files/payment-ok.json
{ "status": "ok", "reference": "ref-123" }
```

Conditional matching fields (compose any of them):

- `method`, `url` / `urlPath` / `urlPathPattern` (regex) — request target.
- `headers` — per-header matchers: `equalTo`, `contains`, `matches` (regex),
  `doesNotMatch`, `caseInsensitive`.
- `queryParameters` — same matcher types keyed by query param name.
- `bodyPatterns` — `equalToJson` (with `ignoreArrayOrder`,
  `ignoreExtraElements`), `matchesJsonPath`, `equalToXml`, `matches` (regex),
  `contains`.
- `scenarioName` + `requiredScenarioState` — conditional on flow state.
- `priority` — lower number wins when multiple mappings match.

### Dynamic stubs via the WireMock REST API

Stub the external API from Vitest by POSTing stubs to WireMock's admin API (any
HTTP client works):

```ts
// test/helpers/wiremock.ts
const WM = 'http://0.0.0.0:8080'

export async function stubPaymentOk() {
  await fetch(`${WM}/__admin/mappings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      request: { method: 'POST', urlPath: '/payments' },
      response: { status: 200, jsonBody: { status: 'ok' } },
    }),
  })
}

export async function resetWiremock() {
  await fetch(`${WM}/__admin/mappings/reset`, { method: 'POST' })
}
```

Rules:

- Point the adapter/config base URL at the WireMock server (e.g.
  `PAYMENT_API_URL=http://0.0.0.0:8080`).
- `resetWiremock()` in `beforeEach` so dynamic stubs never leak between tests.
  Static mappings reload on server restart; delete them from `mappings/` when
  obsolete.
- Verify call counts via WireMock's request journal:
  `GET ${WM}/__admin/requests` and filter by method/url, or use the
  `findRequests` query for exact-match assertions.
- For stateful flows, use WireMock scenarios (a `scenarioName` plus
  `requiredScenarioState`/`newScenarioState`) to drive multi-step sequences.

## Full-Stack Example

```ts
import { beforeEach, describe, expect, it } from 'vitest'
import { createApp } from '../src/app'
import { testDb, migrateTestDb } from './setup-db'
import { stubNotifyOk, resetWiremock } from './helpers/wiremock'

describe('register flow (integration)', () => {
  beforeEach(async () => {
    await migrateTestDb()
    await resetWiremock()
    await stubNotifyOk()
  })

  it('registers a user and notifies the external service', async () => {
    const app = createApp({ db: testDb })

    const res = await app.request('/api/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'a@b.com', password: 'secret' }),
    })

    expect(res.status).toBe(201)
    // external API was called once (via WireMock request journal or assertion)
  })
})
```

## Golden Files & Fixtures

Compare actual results against reviewed "golden" expected outputs instead of
inlining expectations in the test body. This catches unexpected changes in the
response shape across the whole flow.

Layout:

```text
test/integration/
├── users.test.ts
├── setup-db.ts
├── helpers/
│   └── wiremock.ts
└── testdata/
    ├── golden/
    │   ├── users_register_ok.json     # expected handler response
    │   └── users_register_error.json
    ├── fixtures/
    │   └── payment_api.json           # WireMock stub response bodies
    └── wiremock/
        ├── mappings/
        │   └── payment.json           # conditional request → response stubs
        └── __files/
            └── payment-ok.json        # static response bodies referenced by mappings
```

Golden file helper:

```ts
// test/helpers/golden.ts
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'

const update = process.env.UPDATE_GOLDEN === '1'
const base = join(import.meta.dirname, '..', 'testdata', 'golden')

export function assertGolden(name: string, got: string) {
  const path = join(base, name)
  if (update) {
    mkdirSync(dirname(path), { recursive: true })
    writeFileSync(path, got)
    return
  }
  const want = readFileSync(path, 'utf-8')
  expect(JSON.parse(want)).toEqual(JSON.parse(got)) // normalized compare
}
```

Usage:

```ts
import { assertGolden } from './helpers/golden'

it('returns the canonical register response', async () => {
  const res = await app.request('/api/users', { method: 'POST', body: validBody })
  assertGolden('users_register_ok.json', await res.text())
})
```

Conventions for golden files:

- Golden files are **reviewed artifacts**: after adding or changing a flow, run
  `UPDATE_GOLDEN=1 npx vitest run test/integration`, then manually review the
  diff of `testdata/golden/` before committing. Never accept an updated golden
  file without reading it.
- One golden file per flow/outcome: success, validation error, not-found, etc.
- Use `describe`/`it` per case and name goldens consistently:
  `users_register_ok.json`, `users_register_invalid_email.json`.
- Fixtures (input payloads, WireMock stub response bodies) live under
  `testdata/fixtures/` and are read with `readFileSync`, never hardcoded into
  the test.
- WireMock static stubs live under `testdata/wiremock/mappings/*.json` (with
  response bodies in `testdata/wiremock/__files/`), mounted into the container.
  Review mapping changes in git like any other code.
- Prefer deterministic output in goldens: sort JSON keys, fix any timestamps,
  and avoid values that change per run. If the API returns a generated ID,
  normalize it (e.g. replace with a placeholder) before comparing — or assert
  it with `expect.any(String)` instead of a golden.

## Conventions

- Integration tests live under `test/integration/`, separate from unit and
  functional tests.
- One test per user-facing flow, not per function.
- Build the wiring in a shared `setup` helper mirroring `createApp()`,
  returning the app and cleanup.
- Assert the final outcome (status code, persisted state in the in-memory DB,
  external call count via WireMock journal) — not layer internals.
- Always clean up: `beforeEach`/`afterEach` reset the DB and WireMock stubs.
- Prefer docker/testcontainers to launch WireMock so tests are reproducible.
- Compare full flow output with golden files, not inline literals; review the
  golden diff on every `UPDATE_GOLDEN=1` run.

## Verification

- `npx vitest run test/integration` must pass.
- `UPDATE_GOLDEN=1 npx vitest run test/integration` regenerates goldens;
  review the diff in `testdata/golden/` before committing.
- Requires the WireMock server running (or testcontainers starting it).
- A test that needs the real Postgres (not in-memory SQLite) is a different
  beast — run that suite separately against provisioned infra, and keep it out
  of the default `vitest run` path (use a separate config or `--project`).
