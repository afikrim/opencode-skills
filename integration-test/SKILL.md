---
name: integration-test
description: Write integration tests in Go that verify the real wiring of the application layers (handler → service → adapter) while mocking external infrastructure — the database connection via go-sqlmock and external HTTP dependencies via WireMock — comparing actual results against golden files and fixtures. Use when the user asks to test components working together end-to-end, add *_test.go files that exercise the full stack, set up go-sqlmock and go-wiremock, or compare response output with golden files. Triggers on "integration test", "test the full stack", "test handler to database", "mock db with sqlmock", "mock external api with wiremock", "golden file", "fixtures".
---

# Integration Tests (Go)

An integration test verifies that the application layers **work together
through the real wiring** — `handler → service → adapter`, built exactly like
`main.go` builds them. External infrastructure is **mocked**: the database
connection is mocked with `go-sqlmock`, and external HTTP dependencies are
mocked with **WireMock**.

The code under test runs its real logic at every layer. Only the things
outside the app boundary (DB, third-party HTTP APIs) are fakes.

## What to Integration Test

- The full stack: `httptest` request → handler → service → adapter → (mocked
  DB / mocked external API).
- Flows that cross adapters: a handler whose service calls both a repository
  (mock DB) and a payment/notification API (WireMock).
- The real dependency wiring from `cmd/`: that the production constructor
  graph actually satisfies the ports and behaves as composed.

## Mocking the Database Connection (go-sqlmock)

Mock at the `*sql.DB` boundary. Open the mock, register expectations for every
query/exec the flow triggers, then assert all expectations were met.

```go
package integration_test

import (
    "context"
    "testing"

    "github.com/DATA-DOG/go-sqlmock"
)

func TestFindUserByID(t *testing.T) {
    db, mock, err := sqlmock.New()
    if err != nil {
        t.Fatal(err)
    }
    defer db.Close()

    mock.ExpectQuery(`SELECT id, email FROM users WHERE id = \$1`).
        WithArgs("u1").
        WillReturnRows(sqlmock.NewRows([]string{"id", "email"}).AddRow("u1", "a@b.com"))

    repo := postgresql.NewUserRepository(db)
    u, err := repo.FindByID(context.Background(), "u1")
    if err != nil {
        t.Fatal(err)
    }
    if u.Email != "a@b.com" {
        t.Errorf("email = %q, want %q", u.Email, "a@b.com")
    }

    if err := mock.ExpectationsWereMet(); err != nil {
        t.Error(err)
    }
}
```

Useful matchers:

- `sqlmock.AnyArg()` — accept any value for an argument.
- `mock.ExpectBegin()/ExpectCommit()/ExpectRollback()` — transaction flows.
- `sqlmock.NewErrorResult(err)` / `WillReturnError(...)` — failure paths.
- `mock.ExpectationsWereMet()` — assert the app ran every expected query.

## Mocking External Dependencies (WireMock)

WireMock supports two ways to define stubs:

1. **Dynamic stubs** via the `go-wiremock` client (best when a test needs
   stubs unique to that test, or wants to `Verify` call counts).
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

Static mappings and `go-wiremock` stubs can be mixed: load the stable contract
from files, then add per-test stubs or verify with the client.

### Dynamic stubs via go-wiremock

Stub the external API with the `go-wiremock` client:

```go
package integration_test

import (
    "net/http"
    "testing"

    "github.com/wiremock/go-wiremock"
)

func TestPaymentProvider(t *testing.T) {
    wm := wiremock.NewClient("http://0.0.0.0:8080")
    defer wm.Reset()

    stub := wiremock.Post(wiremock.URLPathEqualTo("/payments")).
        WithBodyPattern(wiremock.EqualToJson(`{"amount": 100}`)).
        WillReturnResponse(
            wiremock.NewResponse().
                WithJSONBody(map[string]interface{}{"status": "ok"}).
                WithStatus(http.StatusOK),
        )
    if err := wm.StubFor(stub); err != nil {
        t.Fatal(err)
    }

    // point the adapter's base URL at the WireMock server and exercise the flow

    verified, _ := wm.Verify(stub.Request(), 1)
    if !verified {
        t.Error("expected the payment API to be called once")
    }
}
```

Rules:

- Point the adapter/config base URL at the WireMock server (e.g.
  `PAYMENT_API_URL=http://0.0.0.0:8080`).
- `defer wm.Reset()` so dynamic stubs never leak between tests. Static mappings
  reloaded on server restart; delete them from `mappings/` when obsolete.
- `wm.Verify(stub.Request(), n)` asserts the app called the external service
  exactly `n` times with the expected shape.
- For stateful flows, use scenarios (`InScenario`,
  `WhenScenarioStateIs`, `WillSetStateTo`) and `defer wm.ResetAllScenarios()`.

## Full-Stack Example

Wire everything the way `main.go` does, swapping only the external boundaries:

```go
func TestRegisterFlow(t *testing.T) {
    db, mock, _ := sqlmock.New()
    defer db.Close()

    mock.ExpectExec(`INSERT INTO users`).WillReturnResult(sqlmock.NewResult(1, 1))

    wm := wiremock.NewClient("http://0.0.0.0:8080")
    defer wm.Reset()
    wm.StubFor(wiremock.Post(wiremock.URLPathEqualTo("/notify")).
        WillReturnResponse(wiremock.NewResponse().WithStatus(http.StatusOK)))

    repo := postgresql.NewUserRepository(db)
    notify := httpclient.NewNotifier("http://0.0.0.0:8080")
    svc := service.NewUserService(repo, notify)
    h := handlershttp.NewHandler(svc)

    req := httptest.NewRequest(http.MethodPost, "/register",
        strings.NewReader(`{"email":"a@b.com"}`))
    rec := httptest.NewRecorder()
    h.Register(rec, req)

    if rec.Code != http.StatusCreated {
        t.Errorf("status = %d, want %d", rec.Code, http.StatusCreated)
    }
    if err := mock.ExpectationsWereMet(); err != nil {
        t.Error(err)
    }
}
```

## Golden Files & Fixtures

Compare actual results against reviewed "golden" expected outputs instead of
inlining expectations in the test body. This catches unexpected changes in the
response shape across the whole flow.

Layout:

```text
test/integration/
├── register_test.go
├── testdata/
│   ├── golden/
│   │   ├── register_ok.json        # expected handler response
│   │   └── register_error.json
│   ├── fixtures/
│   │   ├── user_row.json           # input data for sqlmock rows
│   │   └── payment_api.json        # WireMock stub responses
│   └── wiremock/
│       ├── mappings/
│       │   └── payment.json        # conditional request → response stubs
│       └── __files/
│           └── payment-ok.json     # static response bodies referenced by mappings
```

Golden file pattern:

```go
//go:build integration

package integration_test

import (
    "flag"
    "os"
    "testing"
)

var update = flag.Bool("update", false, "update golden files")

func goldenPath(name string) string {
    return filepath.Join("testdata", "golden", name)
}

func assertGolden(t *testing.T, name string, got []byte) {
    t.Helper()
    path := goldenPath(name)

    if *update {
        if err := os.WriteFile(path, got, 0o644); err != nil {
            t.Fatal(err)
        }
        return
    }

    want, err := os.ReadFile(path)
    if err != nil {
        t.Fatalf("golden file %s missing; run `go test -update`", path)
    }
    if !bytes.Equal(want, got) {
        t.Errorf("%s mismatch:\n want: %s\n got:  %s", name, want, got)
    }
}
```

Usage:

```go
func TestRegisterFlow(t *testing.T) {
    // ... build wiring, run request, read rec.Body ...

    assertGolden(t, "register_ok.json", rec.Body.Bytes())
}
```

Conventions for golden files:

- Golden files are **reviewed artifacts**: after adding or changing a flow, run
  `go test ./test/integration/... -update`, then manually review the diff of
  `testdata/golden/` before committing. Never accept an updated golden file
  without reading it.
- One golden file per flow/outcome: success, validation error, not-found, etc.
- Use `t.Run` per case and name goldens consistently:
  `register_ok.json`, `register_invalid_email.json`.
- Fixtures (input payloads, sqlmock row data, WireMock stub response bodies)
  live under `testdata/fixtures/` and are read with `os.ReadFile`, never
  hardcoded into the test.
- WireMock static stubs live under `testdata/wiremock/mappings/*.json` (with
  response bodies in `testdata/wiremock/__files/`), mounted into the container.
  Review mapping changes in git like any other code.
- Prefer deterministic output in goldens: sort JSON keys, fix any timestamps,
  and avoid values that change per run. If the API returns a generated ID,
  normalize it (e.g. replace with a placeholder) before comparing.

## Conventions

- Integration tests live in an `integration_test` package (e.g.
  `test/integration/`), separate from unit and functional tests.
- One test per user-facing flow, not per function.
- Build the wiring in a shared `setup(t)` helper mirroring `main.go`, returning
  the handler/router and cleanup.
- Assert the final outcome (status code, persisted state via mock expectations,
  external call count via `wm.Verify`) — not layer internals.
- Always clean up: `defer db.Close()`, `defer wm.Reset()`, `defer wm.ResetAllScenarios()`.
- Prefer docker/testcontainers to launch WireMock so tests are reproducible.
- Compare full flow output with golden files, not inline literals; review the
  golden diff on every `-update`.

## Verification

- `go test ./test/integration/...` must pass.
- `go test ./test/integration/... -update` regenerates goldens; review the diff
  in `testdata/golden/` before committing.
- Requires the WireMock server running (or testcontainers starting it).
- A test that needs real Postgres/Redis (not mocked) is a different beast — run
  that suite separately against provisioned infra, and keep it out of the
  default `go test ./...` path.
