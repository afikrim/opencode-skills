---
name: ts-unit-test
description: Write unit tests in TypeScript with Vitest. Use when the user asks to create or review unit tests, test pure functions, add *.test.ts files, or run `vitest run`. Unit tests are scoped to pure functions only: mappers, transformers, helper functions, and zod schemas that need no external dependencies. Triggers on "unit test", "write unit tests", "test this mapper/transformer/helper", "vitest".
---

# Unit Tests (TypeScript / Vitest)

Unit tests are scoped to **pure functions only**: mappers, transformers, and
helper functions that don't need external dependencies.

A unit-testable function:

- Takes input, returns output. No external I/O: no database, network, file
  system, env vars, clock, or randomness.
- Is deterministic: same input → same output, every time.
- Has no injected dependencies — if the function needs a dependency to do its
  job, it is not a unit test target, it is a functional test target.

## What to Unit Test

- **Mappers** — DTO ↔ entity, entity ↔ response, object ↔ object conversions
  (`adapters/<adapter>/dto/mapper.ts`, `handlers/dto/mapper.ts`).
- **Transformers** — value conversions, format transforms, case/encoding
  changes.
- **Helper functions** — pure utilities: validation, string formatting,
  parsing, date math with fixed inputs.
- **Zod schemas** — parsing/validation logic (`config/config.ts`, request
  validators): feed fixed inputs, assert `safeParse` outcomes.

Where they live in the hexagonal layout:

- `src/core/entity/` — pure domain logic and value transforms.
- Mapper/transformer/helper files wherever they are defined — as long as they
  are pure, test them next to the code.

## What NOT to Unit Test

Anything that needs a dependency to run:

- **`src/service/`** — depends on ports; goes to functional tests (even
  with mocked ports).
- **`src/adapters/`** — real Drizzle `db`, Redis client, queue producer.
- **`src/handlers/`** — Hono request/response machinery.
- **`src/config/`** — reading `process.env` (the zod *schema* is unit-testable,
  the module that reads env is not).
- **`api/`** — Vercel Function glue.

## Conventions

- Test file next to the code: `user.mapper.ts` → `user.mapper.test.ts`.
- Name tests for behavior: `describe('toUserResponse', ...)` / `it('maps entity to response', ...)`.
- Use `describe` blocks to group cases; use `it.each` for table-driven cases:

```ts
import { describe, expect, it } from 'vitest'
import { parsePhone } from './phone'

describe('parsePhone', () => {
  it.each([
    ['valid', '+6281234567890', '6281234567890'],
    ['missing prefix', '081234567890', null],
    ['empty', '', null],
  ] as const)('%s', (_name, input, want) => {
    expect(parsePhone(input)).toBe(want)
  })
})
```

- No mocks, no fakes, no test doubles — a pure function needs none.
- Assert exact output, not internals.
- Keep tests hermetic: fixed inputs only, never `Date.now()`, `process.env`,
  or `Math.random()`.

## Config

Add `vitest.config.ts` (ESM projects run natively):

```ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['src/**/*.test.ts'],
    environment: 'node',
  },
})
```

Scripts in `package.json`:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

## Verification

- `npm test` must pass (equivalent to `vitest run`).
- Any single unit test runs offline with no infra:
  `npx vitest run src/handlers/dto/user.mapper.test.ts`.
