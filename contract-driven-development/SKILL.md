---
name: contract-driven-development
description: Contract-driven development with OpenAPI as source of truth — Redocly lint/bundle, oapi-codegen v2 chi-server stub generation, and handler reconciliation. Covers the Shelvara flow (shelvara-contracts/openapi.yaml → shelvara-core/internal/contracts/api.gen.go) as a reference implementation, but applies to any Go + OpenAPI service. Use when editing/adding API endpoints, generating/regenerating the contract stub, guarding drift in CI, or wiring ServerInterface/HandlerWithOptions. Triggers on "contract driven", "contract first", "openapi", "oapi-codegen", "api contract", "ServerInterface", "generate contracts".
---

# Contract-Driven Development

Single OpenAPI file is the **source of truth** for the Shelvara HTTP API. Handlers, models, and routing are generated from it; business logic stays in `shelvara-core/internal/service`. The contract is versioned and drift is reviewable in PRs.

## When to Use

- Adding or changing any HTTP endpoint (path, method, request/response shape, error code, auth).
- Touching `shelvara-core/internal/handlers/http/*`, `shelvara-core/internal/contracts/`, or `shelvara-contracts/`.
- CI fails on `contracts:gen:check` or a reviewer asks to re-generate the stub.
- Planning a new PRD feature (auth, AI, search, reading, lending) — spec first.

## Source of Truth

| Artifact | Location | Role |
|---|---|---|
| Spec | `shelvara-contracts/openapi.yaml` | Full API — auth, dashboard, books, genres, locations/shelves, lending, reading, content, AI. Edit here, nowhere else. |
| Codegen config | `shelvara-contracts/oapi-codegen.yaml` | `package: contracts`, `chi-server: true`, `models: true`, `embedded-spec: true` → `shelvara-core/internal/contracts/api.gen.go` |
| Generated stub | `shelvara-core/internal/contracts/api.gen.go` | `ServerInterface`, `ServerInterfaceWrapper`, `Unimplemented`, models, params, `HandlerWithOptions`. **Committed** — drift shows in PR diff. |
| Contracts readme | `shelvara-contracts/README.md` | Workflow summary and conventions. |
| PRD | `docs/product-requirements/mvp.md` | Business rules, AC codes, data model. OperationIds and error codes trace to PRD sections. |

> Spec stays on **OpenAPI 3.0.3** (not 3.1) — `oapi-codegen v2` does not support 3.1.

## Directory Layout

```text
shelvara/
├── docs/product-requirements/mvp.md   # PRD § references (AC-*, BR)
├── shelvara-contracts/
│   ├── openapi.yaml                   # source of truth (3.0.3)
│   ├── oapi-codegen.yaml              # chi-server + models + embedded-spec
│   ├── openapi.bundled.yaml           # output of contracts:bundle (gitignored or docs)
│   └── README.md
└── shelvara-core/
    ├── internal/contracts/api.gen.go  # generated — DO NOT EDIT
    ├── internal/handlers/http/        # thin glue — reconciled to ServerInterface
    │   ├── handler.go                 # RegisterRoutes
    │   ├── endpoints.go               # one func per operationId
    │   └── dto/{dto.go,mapper.go}     # handler DTOs, never entity directly
    └── cmd/api/main.go                # wiring — HandlerWithOptions or RegisterRoutes
```

## Spec Conventions (Shelvara)

Follow these in `shelvara-contracts/openapi.yaml` — they mirror the existing handler style (`shelvara-core/internal/handlers/http/handler.go:1`):

- **JSON only.** RFC3339 UTC timestamps (`format: date-time`). No other content types.
- **Errors** are `ErrorResponse { error, message }` with `error` enum `INVALID | NOT_FOUND | CONFLICT | UNAUTHORIZED | INTERNAL | AI_UNAVAILABLE` mapping to 400/404/409/401/500/503 (`components/responses/*`, `components/schemas/ErrorResponse`).
- **IDs** are `UUID` (`format: uuid`, alias `components/schemas/Uuid`).
- **Security:** global `security: - cookieAuth: []` (cookie `shelvara_session`), with `security: []` on `POST /auth/setup` and `POST /auth/login`. Document this when adding public routes.
- **OperationId** is required — it becomes the Go method name on `ServerInterface` (`shelvara-core/internal/contracts/api.gen.go:748`).
- **Tags** group routes: `auth`, `dashboard`, `books`, `genres`, `locations`, `shelves`, `lending`, `reading`, `content`, `ai`.
- **Book list query:** `search,status,genre,shelf,sort,order,includeArchived,page,pageSize` — extend via `ListBooksParams` if needed.
- **Paginated lists:** `{ items, total, page, pageSize }`.
- **Optional boundaries** (`/ai/*`, `/search/semantic`): must return `503 AI_UNAVAILABLE` with `ErrorResponse` when unavailable; never required for CRUD (`openapi.yaml:577`).

## Workflow

### 1. Edit the spec

Edit `shelvara-contracts/openapi.yaml` only. Do not hand-edit `api.gen.go`.

- Add `paths` + `components/schemas` + `components/parameters`/`responses` as needed.
- Every new path needs an `operationId` (camelCase, becomes Go method), `tags`, `summary`, and explicit `responses` referencing `components/responses/*`.
- Prefer `$ref` for shared schemas/params/responses over inline duplication.

### 2. Lint

```sh
npm run contracts:lint          # bunx --bun @redocly/cli lint shelvara-contracts/openapi.yaml
```

Fix Redocly errors before generating. This catches broken `$ref`, invalid 3.0.3, missing required fields.

Optional preview bundle:

```sh
npm run contracts:bundle        # → shelvara-contracts/openapi.bundled.yaml (for docs/previews)
```

### 3. Generate

```sh
npm run contracts:gen           # go run github.com/oapi-codegen/oapi-codegen/v2/cmd/oapi-codegen@latest -config shelvara-contracts/oapi-codegen.yaml shelvara-contracts/openapi.yaml
# output: shelvara-core/internal/contracts/api.gen.go (package contracts)
```

Config (`shelvara-contracts/oapi-codegen.yaml:1`):

```yaml
package: contracts
generate:
  chi-server: true
  models: true
  embedded-spec: true
output: shelvara-core/internal/contracts/api.gen.go
```

What generation produces (`shelvara-core/internal/contracts/api.gen.go:1`):

- Models: `BookRequest`, `BookResponse`, `ErrorResponse`, enums with `Valid()` helpers.
- Params: `ListBooksParams`, `ListLendingParams`, etc.
- `ServerInterface` (`api.gen.go:748`) — one method per `operationId`.
- `Unimplemented` (`api.gen.go:894`) — `StatusNotImplemented` stub for incremental adoption.
- `ServerInterfaceWrapper` + `Handler`/`HandlerWithOptions` + `Swagger` spec embedding + chi routing shims.

### 4. Drift guard

```sh
npm run contracts:gen:check     # regenerates to /tmp and diffs — fails if stale
go vet ./...                    # catches interface mismatches
```

CI should run `contracts:gen:check`. Commit the regenerated `api.gen.go` so drift is reviewable.

### 5. Reconcile handlers

The generated interface is the contract. Make the existing handler conform:

- Option A — **Full adoption** (recommended for new services): wire `contracts.HandlerWithOptions` / `contracts.Handler` in `shelvara-core/cmd/api/main.go` instead of the hand-rolled `RegisterRoutes` (`shelvara-core/internal/handlers/http/handler.go:26`):

  ```go
  import (
      "github.com/afikrim/shelvara/core/internal/contracts"
      handlershttp "github.com/afikrim/shelvara/core/internal/handlers/http"
  )
  h := handlershttp.NewHandler(bookSvc, genreSvc, locationSvc, lendingSvc, readingSvc, contentSvc, dashboardSvc)
  // h must implement contracts.ServerInterface (compile check below)
  var _ contracts.ServerInterface = (*handlershttp.Handler)(nil)
  r.Mount("/", contracts.HandlerWithOptions(h, contracts.ChiServerOptions{
      ErrorHandlerFunc: func(w http.ResponseWriter, r *http.Request, err error) {
          // map InvalidParamFormatError / RequiredParamError → 400 INVALID
      },
  }))
  ```

- Option B — **Incremental**: keep `Handler.RegisterRoutes` and make `Handler` implement `contracts.ServerInterface` method-by-method. Each endpoint method signature must match the generated one (e.g., `ListBooks(w http.ResponseWriter, r *http.Request, params contracts.ListBooksParams)`).

Handler rules (see `go-hexagonal-architecture` skill):

- Handlers stay **thin glue** — bind DTO, map DTO→service, call one service method, map result→response DTO, write. No business rules.
- Never encode `entity` directly — use `handlers/http/dto` + `mapper.go`.
- Keep adapter/service layer untouched; they depend on ports, not on contract models.

### 6. Wire and verify

```sh
go build ./...                  # must pass — catches missing ServerInterface methods
npm run contracts:lint
npm run contracts:gen:check
# optional: go test ./... if adding behavior
```

## Adding a New Endpoint — Worked Example

PRD adds `POST /books/{id}/duplicate`:

1. **Spec** (`shelvara-contracts/openapi.yaml`):

   ```yaml
   /books/{id}/duplicate:
     post:
       tags: [books]
       summary: Duplicate a book (copy metadata, new id)
       operationId: duplicateBook
       parameters: [{ $ref: '#/components/parameters/BookId' }]
       responses:
         '201': { description: Duplicated, content: { application/json: { schema: { $ref: '#/components/schemas/BookResponse' } } } }
         '401': { $ref: '#/components/responses/Unauthorized' }
         '404': { $ref: '#/components/responses/NotFound' }
   ```

2. **Lint + gen:**

   ```sh
   npm run contracts:lint && npm run contracts:gen
   ```

3. **Implement** — add to `ServerInterface` conformer (`shelvara-core/internal/handlers/http/book_handler.go`):

   ```go
   var _ contracts.ServerInterface = (*Handler)(nil)
   func (h *Handler) DuplicateBook(w http.ResponseWriter, r *http.Request, id contracts.BookId) {
       // thin: optionally decode body, call h.books.Duplicate(r.Context(), id.String())
       // map entity→dto.ToBookResponse, write 201
   }
   ```

4. **Verify:** `go vet ./... && npm run contracts:gen:check`.

## AI / Optional Boundaries

- `/ai/metadata/suggest`, `/ai/recommendations`, `/search/semantic` are **optional online-only**.
- Handlers/services for these must return `503` with `ErrorResponse{error: AI_UNAVAILABLE, message: "..."}` when the boundary is down — caller falls back to manual flow (never block CRUD).
- Do not make auth, books, lending, or reading depend on AI. Document `503` in the spec per operation.

## PRD Traceability

- Reference PRD sections in spec `summary`/`description` (e.g., `PRD § Lending — AC-800`) and in handler comments.
- Error codes trace to PRD invariants: ISBN uniqueness → `409 CONFLICT`, progress bounds → `400 INVALID`, active lending → `409 CONFLICT`, archived/givenAway filtering respects active-library invariants.

## Verification

- `npm run contracts:lint` — spec valid.
- `npm run contracts:gen:check` — no drift (`api.gen.go` == fresh generation).
- `go build ./...` / `go vet ./...` — handler implements `ServerInterface`, models compile.
- `git diff` shows `openapi.yaml` + `api.gen.go` together in the same commit.

## Troubleshooting

- **Spec is 3.1 but oapi-codegen complains:** downgrade to `openapi: 3.0.3` — v2 does not support 3.1. Convert `type: null` / `$ref` siblings accordingly (use `nullable: true`).
- **Generated method missing:** check `operationId` spelling — it is the Go method name.
- **Chi route conflict:** generated `Handler` mounts at the spec paths verbatim. Do not register overlapping manual routes — use `contracts.HandlerWithOptions` as the single mount.
- **Param binding 400 not firing:** `ServerInterfaceWrapper` calls `ErrorHandlerFunc` on `InvalidParamFormatError`/`RequiredParamError` — wire it in `ChiServerOptions.ErrorHandlerFunc` to return `dto.ErrorResponse{Error: "INVALID"}`.
- **Stale `api.gen.go` in PR:** run `npm run contracts:gen` and commit the file — CI guards against staleness.

## References

- Spec: `shelvara-contracts/openapi.yaml`
- Config: `shelvara-contracts/oapi-codegen.yaml`
- Generated: `shelvara-core/internal/contracts/api.gen.go`
- Handlers: `shelvara-core/internal/handlers/http/handler.go`, `endpoints.go`, `dto/mapper.go`
- Wiring: `shelvara-core/cmd/api/main.go`
- PRD: `docs/product-requirements/mvp.md`
