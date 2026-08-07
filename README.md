# opencode-skills

Personal collection of [opencode](https://opencode.ai) skills.

## Installation

Clone this repo and register it via `skills.paths`:

```sh
git clone git@github.com:afikrim/opencode-skills.git ~/.config/opencode/opencode-skills
```

Then add to `opencode.json`:

```json
{
  "skills": {
    "paths": ["opencode-skills"]
  }
}
```

Restart opencode.

## Skills

Skills are grouped by domain. The loader scans recursively, so nesting works
out of the box — `go-backend-engineer/<skill>/SKILL.md` is discovered the same
as a top-level skill.

### go-backend-engineer

- **go-hexagonal-architecture** — Go hexagonal (ports & adapters) layout with thin
  handlers/adapters (no tests needed) and dto+mapper patterns.
- **go-unit-test** — unit tests scoped to pure functions only: mappers,
  transformers, helpers.
- **go-functional-test** — functional tests for the business logic implementation
  (service layer), with ports mocked.
- **go-integration-test** — full-stack wiring tests with go-sqlmock (mock DB) and
  WireMock (mock external APIs), compared against golden files/fixtures.
- **go-monitoring** — observability for Go services: zap structured logging,
  OpenTelemetry traces, Prometheus metrics, pprof + Pyroscope profiling.

### General (language-agnostic)

- **grafana** — local Grafana setup via docker compose with a full observability
  stack (Prometheus, Loki, Tempo, Pyroscope) and provisioning as code.

### nodejs-vercel-backend-engineer

- **ts-hexagonal-architecture** — TypeScript hexagonal (ports & adapters) layout
  on Vercel: single `api/[[route]].ts` catch-all Function mounting a Hono app,
  Drizzle ORM, thin handlers/adapters, dto+mapper patterns.
- **ts-unit-test** — Vitest unit tests scoped to pure functions only: mappers,
  transformers, helpers, zod schemas.
- **ts-functional-test** — Vitest functional tests for the business logic
  implementation (service layer), with ports mocked via `vi.fn()`.
- **ts-integration-test** — Vitest full-stack wiring tests with Drizzle against
  in-memory SQLite and external HTTP via WireMock, compared against golden
  files/fixtures.
- **ts-monitoring** — push-based observability for Vercel serverless: pino
  logging, OpenTelemetry OTLP (Vercel Observability), Pyroscope profiling.

## License

MIT
