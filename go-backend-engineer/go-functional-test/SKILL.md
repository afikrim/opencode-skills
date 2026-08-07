---
name: go-functional-test
description: Write functional tests in Go for the business logic implementation. Use when the user asks to test whether a Go function or feature fulfills its functional requirement, add *_test.go files for Go services or use cases, or verify business logic behavior with mocked dependencies. Functional tests only test the business logic implementation (service layer) — they may mock the function's requirements (ports). Handlers are presentation-only and adapters are thin glue; neither is a functional test target. Triggers on "functional test", "test this requirement", "test the service", "does this work as specified".
---

# Functional Tests (Go)

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
`internal/service/` layer. That is where the use cases and functional
requirements actually live.

- **`internal/service/`** — the ONLY target. A service implements a use case
  (e.g. "register a user") and depends on ports; mock the ports and assert the
  requirement.
- **`internal/core/`** — any domain function with a cross-cutting requirement
  that involves state or collaborators.
- Multi-step flows: "given X, when Y runs, then Z happens".

### What NOT to functional test

- **`internal/adapters/`** — thin glue by design (see Thin Adapters below). All
  testable logic is extracted into pure mappers/transformers, which are unit
  tests. Adapter behavior against real infra belongs in integration tests.
- **`internal/handlers/`** — presentation only: translate the transport
  request, call the service, map the response. Not functional test targets.
  At most a couple of smoke tests if a handler holds non-trivial logic worth
  pinning (with the service port mocked via `httptest`).

## Thin Adapters

Adapters should be so thin there is nothing to test. The pattern:
**adapter = driver call + delegate to an extracted pure function.**

```go
// adapter.go — thin: driver interaction + delegation only
func (r *UserRepository) FindByID(ctx context.Context, id string) (entity.User, error) {
    row := r.db.QueryRowContext(ctx, queryFindByID, id)
    return scanUser(row) // pure function, defined in mapper.go
}
```

- All logic (row→entity mapping, null handling, defaults) lives in pure
  functions like `scanUser`, which take a small interface (e.g. `RowScanner`)
  instead of driver types — those become **unit tests**.
- The adapter keeps only: the driver call, the extract-before-return, and
  error pass-through (`errors.Is(err, sql.ErrNoRows)` → port sentinel).
- Zero business rules in adapters — anything that makes a decision goes to
  entity/service.
- Keep adapter functions ≤ ~5 lines. A reviewer flagging longer ones catches
  logic sneaking in.

Net result: unit tests cover the mappers, functional tests cover the service,
integration tests cover the real driver contract — the adapter is glue nobody
needs to test.

## Mocking the Function's Requirements

Mock at the port boundary, never the business logic under test. Fake the
service dependency ports (repositories, cache, publishers) with hand-rolled
fakes or a mocking library.

Hand-rolled fakes first; they are explicit and dependency-free:

```go
type fakeUserRepo struct{ users map[string]entity.User }

func (f *fakeUserRepo) FindByID(id string) (entity.User, error) {
    if u, ok := f.users[id]; ok {
        return u, nil
    }
    return entity.User{}, ports.ErrNotFound
}

func (f *fakeUserRepo) Save(u entity.User) error {
    f.users[u.ID] = u
    return nil
}
```

Requirement-style service test:

```go
func TestUserServiceRegister(t *testing.T) {
    repo := &fakeUserRepo{users: map[string]entity.User{}}
    svc := service.NewUserService(repo)

    req := service.RegisterRequest{ID: "u1", Email: "a@b.com"}

    if err := svc.Register(context.Background(), req); err != nil {
        t.Fatal(err)
    }

    u, ok := repo.users["u1"]
    if !ok {
        t.Fatal("requirement failed: user must be saved after Register")
    }
    if u.Email != "a@b.com" {
        t.Errorf("saved email = %q, want %q", u.Email, req.Email)
    }
}
```

## Conventions

- Test file next to the code under test: `user_service.go` →
  `user_service_test.go`.
- Name tests by requirement/behavior: `TestUserServiceRegister_SavesUser`.
- Arrange → Act → Assert (Given → When → Then) layout in each test.
- Mock only the immediate dependencies of the business logic under test. Do not
  mock its own logic.
- Assert the requirement outcome (return value, state change, recorded call),
  not implementation details.
- Keep mocked-data fixtures tiny and explicit per test.

## Verification

- `go test ./...` must pass.
- `go test -race ./internal/...` for concurrency-sensitive code.
- Functional tests still run offline — mocked ports mean no real infra:
  `go test ./internal/service/ -run TestUserServiceRegister`.
- If a test needs real Postgres/Redis/network, it is no longer functional — it
  belongs in an integration test.
