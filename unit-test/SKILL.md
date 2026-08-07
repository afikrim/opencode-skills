---
name: unit-test
description: Write unit tests in Go. Use when the user asks to create or review unit tests, test functions, add *_test.go files, or run `go test`. Unit tests are scoped to pure functions only: mappers, transformers, and helper functions that need no external dependencies. Triggers on "unit test", "write unit tests", "test this mapper/transformer/helper".
---

# Unit Tests (Go)

Unit tests are scoped to **pure functions only**: mappers, transformers, and
helper functions that don't need external dependencies.

A unit-testable function:

- Takes input, returns output. No external I/O: no database, network, file
  system, env vars, clock, or randomness.
- Is deterministic: same input → same output, every time.
- Has no injected dependencies — if the function needs a dependency to do its
  job, it is not a unit test target, it is a functional test target.

## What to Unit Test

- **Mappers** — DTO ↔ entity, entity ↔ response, struct ↔ struct conversions.
- **Transformers** — value conversions, format transforms, case/encoding
  changes.
- **Helper functions** — pure utilities: validation, math, string formatting,
  parsing, date math with fixed inputs.

Where they live in the hexagonal layout:

- `internal/core/entity/` — pure domain logic and value transforms.
- Mapper/transformer/helper files wherever they are defined — as long as they
  are pure, test them next to the code.

## What NOT to Unit Test

Anything that needs a dependency to run:

- **`internal/service/`** — depends on ports; goes to functional tests (even
  with mocked ports).
- **`internal/adapters/`** — real `*sql.DB`, Redis client, queue producer.
- **`internal/handlers/`** — HTTP request/response machinery.
- **`internal/config/`**, **`cmd/`**, anything reading env or shelling out.

## Conventions

- Test file next to the code: `user_mapper.go` → `user_mapper_test.go`.
- Name tests for behavior: `TestToResponse`, `TestParsePhone`.
- Table-driven tests for multiple cases:

```go
func TestParsePhone(t *testing.T) {
    cases := []struct {
        name   string
        input  string
        want   string
        wantErr bool
    }{
        {"valid", "+6281234567890", "6281234567890", false},
        {"missing prefix", "081234567890", "", true},
        {"empty", "", "", true},
    }
    for _, tc := range cases {
        t.Run(tc.name, func(t *testing.T) {
            got, err := parsePhone(tc.input)
            if (err != nil) != tc.wantErr {
                t.Fatalf("parsePhone() error = %v, wantErr %v", err, tc.wantErr)
            }
            if got != tc.want {
                t.Errorf("parsePhone() = %q, want %q", got, tc.want)
            }
        })
    }
}
```

- No mocks, no fakes, no test doubles — a pure function needs none.
- Assert exact output, not internals.
- Keep tests hermetic: fixed inputs only, never time.Now(), os.Getenv, or
  rand.

## Verification

- `go test ./...` must pass.
- Any single unit test runs offline with no infra:
  `go test ./internal/core/entity/ -run TestParsePhone`.
