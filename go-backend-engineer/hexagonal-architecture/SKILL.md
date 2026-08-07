---
name: hexagonal-architecture
description: Structure Go applications using hexagonal (ports & adapters) architecture with thin handlers and adapters designed so they need no tests, and dto+mapper patterns so no layer leaks entity models into external dependencies or presentation. Use when the user asks to scaffold a Go service, organize code into cmd/internal/core/ports/service/adapters/handlers layers, define domain entities and ports, implement adapters (postgresql, redis, queue, etc.), build HTTP/REST handlers, or wire up an application with godotenv + caarlos0/env config. Triggers on "hexagonal architecture", "ports and adapters", "scaffold a Go service", "clean architecture in Go".
---

# Hexagonal Architecture (Go)

Apply this layout whenever scaffolding or extending a Go application.

## Directory Layout

```text
<project>/
├── cmd/<program>/
│   └── main.go                # entrypoint: load config, wire deps, start server
├── internal/
│   ├── core/
│   │   ├── entity/<entity>.go # domain entities, value types, enums
│   │   └── ports/<interface>.go # interfaces (contracts), grouped by use
│   ├── service/<service>.go   # service layer, implements use cases
│   ├── adapters/
│   │   └── <adapter>/         # postgresql, redis, queue, mock, ...
│   │       ├── <adapter>.go   # thin impl, calls dto mappers
│   │       └── dto/
│   │           ├── <dto-model>.go # adapter's own model
│   │           └── mapper.go  # pure entity↔dto mappers
│   ├── handlers/
│   │   └── <handler>/         # any presentation entry: http, channel, grpc,
│   │       ├── handler.go     # websocket, cli, ... one folder per handler
│   │       ├── registration.go
│   │       ├── logout.go
│   │       └── dto/
│   │           ├── <dto-model>.go # request/response models
│   │           └── mapper.go  # pure dto↔service/entity mappers
│   └── config/config.go       # app config loaded via godotenv + caarlos0/env
```

## Layer Responsibilities

### 1. `cmd/<program>/main.go`

- Load config (`config.Load()`), panic/fatal on error.
- Construct adapters first, then services, then handlers.
- Wire dependencies by satisfying ports with concrete implementations.
- Start the HTTP server / worker / queue consumer.

### 2. `internal/core/entity/<entity>.go`

- Pure domain types: structs, value objects, enums, constants.
- No database, HTTP, or framework imports. No `*sql.DB`, `context.Context`
  leakage into domain logic beyond what the domain needs.
- Domain logic (business rules that apply everywhere) lives here.

### 3. `internal/core/ports/<interface>.go`

Interfaces are the contracts, owned by the core. Two kinds, both declared here:

- **Service dependency ports**: interfaces the service layer requires from its
  dependencies (e.g. `UserRepository`, `CacheRepository`, `Publisher`). The
  service depends on these interfaces, not concrete adapters.
- **Handler dependency ports**: interfaces the handler layer requires from
  services (e.g. `UserService`, `OrderService`). Handlers depend on these
  interfaces, not concrete service implementations.

Naming: `Name + role`, e.g. `UserRepository`, `CacheStore`, `MessagePublisher`.

### 4. `internal/service/<service>.go`

- Implements the use cases the handlers need.
- Depends on **ports** (service dependency interfaces), never on concrete
  adapters directly.
- Receives its dependencies via constructor injection:
  `func NewUserService(repo ports.UserRepository) *UserService`.
- Implements the **handler dependency ports** declared in
  `internal/core/ports/`.
- Keeps orchestration here: validation of domain rules, transaction boundaries,
  calling repository/publisher/cache ports.

### 5. `internal/adapters/<adapter>/...`

Adapters are **thin glue** — designed so they never need testing.

- One folder per adapter type (postgresql, redis, queue, mock, ...).
- Implements the service dependency ports for a concrete technology:
  `internal/adapters/postgresql/user_repository.go`,
  `internal/adapters/redis/cache_store.go`,
  `internal/adapters/queue/publisher.go`.
- Holds the concrete `*sql.DB`, Redis client, queue producer, etc.
- Constructor takes its own deps: `func NewUserRepository(db *sql.DB) *UserRepository`.

**Adapters own their own model — never the entity directly.** Each adapter has a
`dto/` package:

- `internal/adapters/<adapter>/dto/<dto-model>.go` — the adapter's data model
  (SQL row shape, Redis value shape, queue payload shape).
- `internal/adapters/<adapter>/dto/mapper.go` — the pure entity↔DTO mappers
  (`dto.FromEntity(u entity.User) dto.UserDTO`,
  `dto.ToEntity(d UserDTO) (entity.User, error)`).
- The port interface the adapter implements **still uses entity types**. Only
  the adapter implementation maps entity ↔ DTO, and the mapping is called
  inside the adapter methods.

```go
// dto/user.go — adapter's own model
type UserDTO struct {
    ID    string
    Email string
}

// dto/mapper.go — pure entity↔dto mappers
func FromEntity(u entity.User) UserDTO {
    return UserDTO{ID: u.ID, Email: u.Email}
}

func ToEntity(d UserDTO) (entity.User, error) {
    if d.ID == "" {
        return entity.User{}, errors.New("user dto: empty id")
    }
    return entity.User{ID: d.ID, Email: d.Email}, nil
}
```

Thin-adapter pattern — the adapter method is only:

1. map entity → DTO (before the driver call);
2. driver call (`QueryRow`, `Exec`, `Publish`, ...);
3. extract/scan the DTO;
4. map DTO → entity (after the driver call);
5. error pass-through (`errors.Is(err, sql.ErrNoRows)` → port sentinel).

```go
// user_repository.go — thin: entity↔DTO mapped inside the adapter
func (r *UserRepository) FindByID(ctx context.Context, id string) (entity.User, error) {
    var d dto.UserDTO
    err := r.db.QueryRowContext(ctx, queryFindByID, id).Scan(&d.ID, &d.Email)
    if errors.Is(err, sql.ErrNoRows) {
        return entity.User{}, ports.ErrNotFound
    }
    if err != nil {
        return entity.User{}, err
    }
    return dto.ToEntity(d) // entity comes out of the adapter
}

func (r *UserRepository) Save(ctx context.Context, u entity.User) error {
    d := dto.FromEntity(u) // entity goes in, DTO hits the driver
    _, err := r.db.ExecContext(ctx, querySave, d.ID, d.Email)
    return err
}
```

- DTOs are pure structs; the entity↔DTO mappers are pure functions — both are
  unit-test targets.
- Zero business rules in adapters — anything that makes a decision goes to
  entity/service.
- Keep adapter functions ≤ ~5 lines; longer means logic is sneaking in.

### 6. `internal/handlers/<handler>/...`

The presentation layer, one folder per **handler/entry type**. `<handler>` can be
anything the app exposes: `http`, `channel`, `grpc`, `websocket`, `cli`, `cron`,
... Each folder has a `handler.go` root file plus one file per endpoint.

- `internal/handlers/http/handler.go` — HTTP root file that registers the router
  and maps each endpoint to its handler:
  `r.Post("/register", h.Register)`, `r.Post("/logout", h.Logout)`.
- `internal/handlers/http/registration.go` — one HTTP endpoint, one file.
- `internal/handlers/channel/handler.go` — root file mapping queue/channel
  messages to handlers.
- `internal/handlers/channel/publish-message.go` — one channel consumer.
- `internal/handlers/grpc/...`, `internal/handlers/cli/...`, etc. follow the
  same shape.

Per-endpoint handler rules:

- Depends on **handler dependency ports** (the service interfaces), injected via
  constructor: `func NewUserHandler(svc ports.UserService) *UserHandler`.
- Translates the transport's request → service call → transport response. No
  database or adapter access here.
- `handler.go` exposes `NewHandler(svc ports.UserService) *Handler` and
  `RegisterRoutes(r *chi.Mux, h *Handler)` (or the transport's equivalent) for
  wiring in `main.go`.

**Handlers own their own model — never the entity directly.** Each handler has
a `dto/` package plus pure mappers:

- `internal/handlers/<handler>/dto/<dto-model>.go` — request/response models
  for the presentation layer (JSON/HTTP shapes, channel payloads, CLI args).
- `internal/handlers/<handler>/dto/mapper.go` — pure mappers between the DTOs
  and the service/entity types.
- The handler dependency port (service interface) still uses service/entity
  types. The handler binds a DTO, maps to a service request, calls the service,
  and maps the result to a response DTO.

```go
// dto/user.go — presentation's own model
type RegisterRequest struct {
    Email    string `json:"email"`
    Password string `json:"password"`
}

// dto/mapper.go — pure mappers: dto ↔ service
func (r RegisterRequest) ToService() service.RegisterRequest {
    return service.RegisterRequest{Email: r.Email, Password: r.Password}
}

func ToUserResponse(u entity.User) dto.UserResponse {
    return dto.UserResponse{ID: u.ID, Email: u.Email}
}
```

Handlers are **thin glue** — designed so they never need testing. The handler
body is only:

1. bind/parse the transport input into a request DTO;
2. map request DTO → service request;
3. call one service method;
4. map the result → response DTO;
5. write the transport response.

```go
func (h *UserHandler) Register(w http.ResponseWriter, r *http.Request) {
    var req dto.RegisterRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, "bad request", http.StatusBadRequest)
        return
    }
    u, err := h.svc.Register(r.Context(), req.ToService())
    if err != nil {
        http.Error(w, "internal error", http.StatusInternalServerError)
        return
    }
    json.NewEncoder(w).Encode(ToUserResponse(u)) // never encode an entity
}
```

- All validation, DTO/response mapping, and auth extraction with real logic
  goes into **pure functions** (unit-test targets) — never inline in the
  handler.
- Zero business rules in handlers; they decide nothing, they only translate.
- Keep handler bodies ~10 lines; longer means logic is sneaking in.

### 7. `internal/config/config.go`

```go
package config

import (
    "log"

    "github.com/caarlos0/env/v11"
    "github.com/joho/godotenv"
)

type Config struct {
    Port string `env:"PORT" envDefault:"8080"`

    Database struct {
        Host     string `env:"HOST,required"`
        Port     int    `env:"PORT,required"`
        User     string `env:"USER,required"`
        Password string `env:"PASSWORD,required"`
        Name     string `env:"NAME,required"`
    } `envPrefix:"DB_"`

    Redis struct {
        Addr string `env:"ADDR,required"`
    } `envPrefix:"REDIS_"`
}

func Load() (*Config, error) {
    // Load .env values (does NOT override already-set process vars).
    if err := godotenv.Load(); err != nil {
        log.Println("warning: no .env file found, using environment")
    }

    cfg := &Config{}
    if err := env.Parse(cfg); err != nil {
        return nil, err
    }
    return cfg, nil
}
```

Rules for config:

- `godotenv.Load()` as close to startup as possible, in `config.Load()`.
- `env.Parse(&cfg)` fills the struct from `os.Environ()`, applying
  `envDefault` defaults and failing on `env:"...,required"` fields missing from
  the environment.
- Use `envPrefix:"DB_"`, `envPrefix:"REDIS_"` on nested structs to namespace
  groups: expects `DB_HOST`, `REDIS_ADDR`, etc.
- Required connection params are `,required`; optional tuning knobs get
  `envDefault`.

## Wiring Example (`cmd/api/main.go`)

```go
func main() {
    cfg, err := config.Load()
    if err != nil {
        log.Fatal(err)
    }

    db := postgresql.New(cfg.Database)
    repo := postgresql.NewUserRepository(db)
    svc := service.NewUserService(repo)
    h := handlershttp.NewHandler(svc)

    r := chi.NewRouter()
    handlershttp.RegisterRoutes(r, h)
    http.ListenAndServe(":"+cfg.Port, r)
}
```

## Testing Strategy

This layout is designed so the **only tested layers are pure functions
(unit) and the business logic (functional)**. Handlers and adapters are thin
glue and are not test targets.

- **Unit tests** — the extracted pure functions: entity↔DTO mappers
  (`adapters/<adapter>/dto/mapper.go`, `handlers/<handler>/dto/mapper.go`),
  transformers, helpers, and validators.
- **Functional tests** — the business logic implementation (`internal/service/`)
  with ports mocked.
- **Integration tests** — real driver contracts (Postgres, Redis, queue)
  exercised against real infra; covers adapter/driver wiring end-to-end.
- Handlers and adapters themselves get no dedicated tests — their logic lives
  in the pure functions, their requirements live in the service, and their
  driver contract lives in integration tests.

## Dependency Direction

```text
cmd → config, adapters, service, handlers
handlers → ports (handler dependency interfaces) → service
service → ports (service dependency interfaces) → adapters
core → entity, ports (no outward deps)
```

- Dependencies point **inward**. Core knows nothing about adapters or HTTP.
- Every concrete dependency crosses the boundary only through its port
  interface.
- Swap implementations (postgres ↔ mock, real queue ↔ in-memory) without
  touching service, handlers, or core.

## Naming Conventions

- Ports: `UserRepository`, `CacheStore`, `MessagePublisher`.
- Service impls: `UserService`, `OrderService` implementing `ports.UserService`.
- Adapters: `postgresql.UserRepository`, `redis.CacheStore`, `queue.Publisher`.
- Handlers: package per entry type (`handlers/http`, `handlers/channel`,
  `handlers/grpc`, ...), with `handler.go` as the root/route-mapping file.
- DTOs: `dto.UserDTO`, `dto.RegisterRequest`, `dto.UserResponse` — one `dto/`
  package per adapter and per handler. Models live in `<dto-model>.go`, the
  pure mappers (`FromEntity`, `ToEntity`, `ToService`) live in `dto/mapper.go`.

## Verification

- `go build ./...` must pass.
- Confirm no `*sql.DB`, Redis client, or HTTP types leak into `core/`.
- Confirm services receive ports, not adapters; handlers receive ports, not
  service concrete types.
- Confirm adapters and handlers are thin: no business rules, no inline mapping
  logic, functions within the size limits above.
- Confirm adapters never touch `entity` types directly — only via
  `adapters/<adapter>/dto/` mappers. Port interfaces keep using entity.
- Confirm handlers never encode/accept `entity` types directly — only via
  `handlers/<handler>/dto/` models and `dto/mapper.go`.
- Confirm the DTOs and mappers are pure and unit-testable (no driver/HTTP types
  in their signatures).
