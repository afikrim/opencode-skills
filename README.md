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

### nodejs-backend-engineer

Generic TypeScript backend skills (runnable anywhere Node runs).

- **ts-hexagonal-architecture** — TypeScript hexagonal (ports & adapters) layout
  with Hono, Drizzle ORM, thin handlers/adapters, dto+mapper patterns, entry
  via `hono/node-server`.
- **ts-unit-test** — Vitest unit tests scoped to pure functions only: mappers,
  transformers, helpers, zod schemas.
- **ts-functional-test** — Vitest functional tests for the business logic
  implementation (service layer), with ports mocked via `vi.fn()`.
- **ts-integration-test** — Vitest full-stack wiring tests with Drizzle against
  in-memory SQLite and external HTTP via WireMock, compared against golden
  files/fixtures.
- **ts-monitoring** — observability for long-running Node/Hono services: pino
  logging, OpenTelemetry, Prometheus pull + OTLP push, Pyroscope profiling.

### nodejs-vercel-backend-engineer

Vercel layer on top of `nodejs-backend-engineer` — only the platform-specific
parts (entrypoint, deployment, serverless observability) live here.

- **ts-vercel-architecture** — deploy the `ts-hexagonal-architecture` app to
  Vercel: single `api/[[route]].ts` catch-all Function mounting the Hono app
  via `hono/vercel`'s `handle()`, edge/nodejs runtime, `vercel dev`/deploy.
- **ts-vercel-monitoring** — push-based observability for Vercel serverless:
  Vercel Observability + OTLP export (no scrape ports), pino logging, Pyroscope
  profiling — on top of the generic `ts-monitoring`.

### nodejs-nextjs-engineer

- **nextjs-architecture** — optimal Next.js (App Router) implementation:
  server-first with React Server Components, data fetching/caching, Server
  Actions, route groups, client/server boundaries.
- **nextjs-api-decision** — decide where backend logic lives: RSC + Server
  Actions vs Route Handlers vs separate API vs plain React, with a decision
  tree and worked examples.
- **nextjs-api-architecture** — hexagonal (ports & adapters) structure for the
  backend inside Next.js: one service layer shared by Route Handlers, Server
  Actions, and RSC pages, with thin entrypoints and dto/mapper patterns.
- **nextjs-testing** — Vitest unit/component tests (RTL) + Playwright E2E;
  mocking next/navigation, next/headers, and Server Actions.
- **nextjs-monitoring** — Web Vitals (useReportWebVitals / Vercel Analytics),
  OpenTelemetry server tracing via instrumentation.ts, errors & structured
  logging.

## License

MIT
