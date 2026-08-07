---
name: ts-functional-test
description: Write functional tests in TypeScript for the business logic implementation. Use when the user asks to test whether a TypeScript function or feature fulfills its functional requirement, add *.test.ts files for services or use cases, or verify business logic behavior with mocked dependencies. Functional tests only test the business logic implementation (service layer) — they may mock the function's requirements (ports). Handlers are presentation-only and adapters are thin glue; neither is a functional test target. Triggers on "functional test", "test this requirement", "test the service", "does this work as specified".
---

# Functional Tests (TypeScript / Vitest)

A functional test verifies that the **business logic implementation fulfills
its functional requirement** — that it actually does what it is specified to
do. The test **mocks the function's requirements** (its dependencies/ports), so
the business logic runs for real while its collaborators are fakes.

Key distinction from unit tests:

- Unit tests → pure functions (mappers, transformers, helpers), no dependencies.
- Functional tests → the business logic implementation (service layer), with
  dependencies **mocked**.

## What to Functional Test

Functional tests target the **business logic implementation only** — the
`src/service/` layer. That is where the use cases and functional requirements
actually live.

- **`src/service/`** — the ONLY target. A service implements a use case
  (e.g. "register a user") and depends on ports; mock the ports and assert the
  requirement.
- **`src/core/`** — any domain function with a cross-cutting requirement that
  involves state or collaborators.
- Multi-step flows: "given X, when Y runs, then Z happens".

### What NOT to functional test

- **`src/adapters/`** — thin glue by design (see Thin Adapters below). All
  testable logic is extracted into pure mappers/transformers, which are unit
  tests. Adapter behavior against real infra belongs in integration tests.
- **`src/handlers/`** — presentation only: translate the request, call the
  service, map the response. Not functional test targets. At most a couple of
  smoke tests if a handler holds non-trivial logic worth pinning (with the
  service port mocked via Hono's `app.request()`).
- **The entrypoint (`src/index.ts`, `api/[[route]].ts`) — platform glue; never
  a test target.

## Thin Adapters

Adapters should be so thin there is nothing to test. The pattern:
**adapter = driver call + delegate to an extracted pure function.**

```ts
// postgres/user-repository.ts — thin: driver interaction + delegation only
export class PostgresUserRepository implements UserRepository {
  async findById(id: string): Promise<User | null> {
    const rows = await this.db.select().from(usersTable).where(eq(usersTable.id, id)).limit(1)
    return rows.length ? toEntity(rows[0]) : null // pure mapping lives in dto/mapper.ts
  }
}
```

- All logic (row→entity mapping, null handling, defaults) lives in pure
  functions like `toEntity` in `dto/mapper.ts` — those become **unit tests**.
- The adapter keeps only: the driver call, the extract-before-return, and
  error pass-through (no rows → `null`/sentinel).
- Zero business rules in adapters — anything that makes a decision goes to
  entity/service.
- Keep adapter methods ≤ ~5 lines. A reviewer flagging longer ones catches
  logic sneaking in.

Net result: unit tests cover the mappers, functional tests cover the service,
integration tests cover the real driver contract — the adapter is glue nobody
needs to test.

## Mocking the Function's Requirements

Mock at the port boundary, never the business logic under test. Fake the
service dependency ports (repositories, cache, publishers) with hand-rolled
fakes or `vi.fn()`.

Hand-rolled fakes first; they are explicit and dependency-free:

```ts
class FakeUserRepository implements UserRepository {
  users = new Map<string, User>()

  async findById(id: string): Promise<User | null> {
    return this.users.get(id) ?? null
  }

  async save(user: User): Promise<void> {
    this.users.set(user.id, user)
  }
}
```

`vi.fn()` when the port is small or you want call assertions:

```ts
const repo = {
  findById: vi.fn(),
  save: vi.fn(),
}
```

Requirement-style service test:

```ts
import { describe, expect, it } from 'vitest'
import { UserService } from './user-service'

describe('UserService.register', () => {
  it('saves the user when registration succeeds', async () => {
    const repo = new FakeUserRepository()
    const svc = new UserService(repo)

    await svc.register({ id: 'u1', email: 'a@b.com' })

    const saved = repo.users.get('u1')
    expect(saved).toBeDefined()
    expect(saved!.email).toBe('a@b.com')
  })
})
```

## Conventions

- Test file next to the code under test: `user-service.ts` →
  `user-service.test.ts`.
- Name tests by requirement/behavior:
  `describe('UserService.register')` → `it('saves the user')`.
- Arrange → Act → Assert (Given → When → Then) layout in each test.
- Mock only the immediate dependencies of the business logic under test. Do not
  mock its own logic.
- Assert the requirement outcome (return value, state change, recorded call),
  not implementation details.
- Keep mocked-data fixtures tiny and explicit per test.
- Use `beforeEach` to reset fakes when state leaks between tests.

## Verification

- `npm test` must pass (`vitest run`).
- Run the service suite only:
  `npx vitest run src/service/`.
- Functional tests still run offline — mocked ports mean no real infra. If a
  test needs a real DB/Redis/network, it is no longer functional — it belongs
  in an integration test.
