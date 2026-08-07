---
name: ts-monitoring
description: Add observability to TypeScript services deployed on Vercel: structured logging with pino, OpenTelemetry traces/metrics exported via OTLP (push-based, works on Vercel's serverless Functions and Vercel Observability), and continuous profiling with Pyroscope. Use when the user asks to set up logging, tracing, metrics, or profiling in a TypeScript/Hono/Vercel service, or integrate pino, OpenTelemetry, Prometheus-compatible OTLP metrics, or Pyroscope. Triggers on "monitoring", "observability", "structured logging", "open telemetry", "metrics", "profiling", "pyroscope", "pino", "vercel observability".
---

# Monitoring & Observability (TypeScript on Vercel)

Instrument a TypeScript service with observability, aligned with the hexagonal
architecture layout so observability stays in wrappers and never leaks into
business logic.

**Vercel-specific reality check** — this differs from a long-running server:

- Vercel Functions are **serverless and ephemeral**: no persistent process, no
  port to scrape, no long-lived metrics endpoint. A Prometheus pull-style
  server (like the Go skill's `:9090` / pprof `:6060`) does **not** apply.
- Observability must be **push-based**: emit traces/metrics over **OTLP** to a
  collector — Vercel's own Observability (OpenTelemetry) ingestion or a
  third-party backend (Grafana Cloud, Datadog, etc.).
- The same code runs in `vercel dev` locally and on Vercel. Guard config so
  local/test runs either skip export or export to a local collector.

Three pillars:

1. **Structured logging** — pino
2. **Traces & metrics** — OpenTelemetry (OTLP export, `@opentelemetry/sdk-node`)
3. **Profiling** — Pyroscope (serverless-compatible agent)

## Directory Layout

```text
src/
├── observability/
│   ├── logger.ts        # pino logger setup (trace correlation)
│   ├── tracer.ts        # OTLP exporter + resource + NodeSDK init
│   ├── metrics.ts       # OTel metric provider, RED via Hono middleware
│   └── profiling.ts     # Pyroscope agent (best-effort, skip when unset)
```

## 1. Structured Logging (pino)

Use `pino` with JSON output by default. Level comes from env (`LOG_LEVEL`).

```ts
// src/observability/logger.ts
import { pino } from 'pino'

export const logger = pino({
  level: process.env.LOG_LEVEL ?? 'info',
  base: { service: 'my-service' }, // replaces pid/hostname defaults with useful context
})
```

Rules:

- Use the object/field API (`logger.info({ user_id }, 'registration done')`) —
  structured fields, not string interpolation.
- Carry `trace_id`/`span_id` from the active OpenTelemetry span into logs:
  pino does not do this automatically — add a middleware that enriches each
  log call, or use `@opentelemetry/api`'s `trace.getActiveSpan()` to include
  the ids in a child logger.
- Inject the logger into services/handlers as a constructor dependency (same DI
  pattern as the architecture skill) — no global logger in business logic when
  possible.
- Never log secrets, tokens, or full PII. Redact fields with pino's `redact`
  option: `pino({ redact: ['password', 'authorization'] })`.
- Keep field names consistent (`user_id`, not `userID`/`userId`).

## 2. OpenTelemetry (OTLP, push-based)

Set up `@opentelemetry/sdk-node` once, at module load, before the Hono app is
built. Use OTLP HTTP exporters so the same pipeline works with Vercel
Observability, Grafana, Datadog, etc.

```sh
npm i @opentelemetry/sdk-node \
  @opentelemetry/api \
  @opentelemetry/exporter-trace-otlp-http \
  @opentelemetry/exporter-metrics-otlp-http \
  @opentelemetry/resources \
  @opentelemetry/semantic-conventions
```

```ts
// src/observability/tracer.ts
import { NodeSDK } from '@opentelemetry/sdk-node'
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http'
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http'
import { PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics'
import { resourceFromAttributes } from '@opentelemetry/resources'
import { ATTR_SERVICE_NAME, ATTR_SERVICE_VERSION } from '@opentelemetry/semantic-conventions'

export function startTelemetry() {
  if (!process.env.OTEL_EXPORTER_OTLP_ENDPOINT) return // local/test: no export

  const sdk = new NodeSDK({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME ?? 'my-service',
      [ATTR_SERVICE_VERSION]: process.env.OTEL_SERVICE_VERSION ?? '1.0.0',
    }),
    traceExporter: new OTLPTraceExporter(),
    metricReader: new PeriodicExportingMetricReader({
      exporter: new OTLPMetricExporter(),
    }),
  })

  sdk.start()
  return sdk
}
```

### Vercel Observability (first-party option)

Vercel ships first-party OpenTelemetry ingestion. With Vercel Observability
enabled, traces from your Functions appear in the Vercel dashboard and can be
forwarded to third-party backends:

- Enable in the Vercel dashboard (**Observability** tab) or via the
  `enableRequestTracing`/observability settings on your project.
- Vercel instruments the Function wrapper itself; your OTLP exporters send to
  `OTEL_EXPORTER_OTLP_ENDPOINT` (Vercel provides collector env values) and
  `VERCEL` env flag indicates the production environment.
- Keep custom SDK init light so Vercel's own instrumentation and yours compose
  (don't double-start providers; use the API and let Vercel's middleware carry
  the context).

### Instrumentation

- **HTTP (inbound)**: Hono middleware `@hono/otel` (from `hono/otel`) gives
  request spans automatically. Wrap the app: `app.use('*', otel())`.
- **HTTP (outbound, adapters calling external APIs)**: use
  `@opentelemetry/instrumentation-http` auto-instrumentation so external calls
  appear in the trace.
- **DB**: Drizzle queries over an HTTP/TCP driver — instrumentation is driver-
  dependent. `@opentelemetry/instrumentation-undici` (fetch-based drivers like
  neon-http) captures the underlying HTTP calls. For `node-postgres` use
  `@opentelemetry/instrumentation-pg`.

Pattern: instrumentation lives in the **middleware/constructor layer**, so
service and core stay 100% clean of otel imports.

## 3. Metrics (OTLP push)

No local `/metrics` endpoint. Define meters and push with the periodic OTLP
metric reader. RED-method HTTP metrics (Rate, Errors, Duration) come from a
Hono middleware that records into an OTel meter.

```ts
// src/observability/metrics.ts
import { metrics } from '@opentelemetry/api'

const meter = metrics.getMeter('my-service')
export const httpRequests = meter.createCounter('http.requests', {
  description: 'Total HTTP requests',
})
export const httpDuration = meter.createHistogram('http.duration', {
  description: 'Request latency',
})
```

```ts
// middleware on the Hono app
app.use('*', async (c, next) => {
  const start = performance.now()
  await next()
  httpRequests.add(1, { method: c.req.method, status: String(c.res.status) })
  httpDuration.record(performance.now() - start, { method: c.req.method })
})
```

Rules:

- Label cardinality stays bounded — never put user IDs, emails, or free-form
  strings in attributes.
- On Vercel, metric emission is best-effort per invocation; design dashboards
  for sampled/aggregated data rather than per-request exactness.
- For Prometheus-style backends, point the OTLP metric exporter at an
  OpenTelemetry Collector that translates OTLP → Prometheus (e.g. via
  Grafana Cloud or a self-hosted collector). There is no direct scrape target
  on Vercel.

## 4. Profiling (Pyroscope)

Vercel Functions are short-lived and isolated, so **pprof-style on-demand CPU
profiles don't exist** in the same way. Use Pyroscope's Node.js agent for
continuous profiling; it works in serverless by sampling during the
invocation lifetime and pushing to the server.

```sh
npm i @pyroscope/nodejs
```

```ts
// src/observability/profiling.ts
import Pyroscope, { ProfilingEvent } from '@pyroscope/nodejs'

export function startProfiling() {
  if (!process.env.PYROSCOPE_SERVER) return // local/test: no agent

  Pyroscope.init({
    serverAddress: process.env.PYROSCOPE_SERVER, // e.g. http://localhost:4040
    appName: 'my-service{env=production,version=1.0.0}',
    authToken: process.env.PYROSCOPE_AUTH_TOKEN,
  })
  Pyroscope.startCollecting()
}

export async function stopProfiling() {
  if (process.env.PYROSCOPE_SERVER) await Pyroscope.stop()
}

void startProfiling() // fire-and-forget on module load
```

Rules:

- Call `startProfiling()` at module load in the catch-all function, and
  `stopProfiling()` before the handler returns (best-effort flush) — wrap the
  exported handler:

  ```ts
  export default async (req: Request) => {
    try {
      return await handle(app)(req)
    } finally {
      await stopProfiling()
    }
  }
  ```

- Skip the agent entirely when `PYROSCOPE_SERVER` is unset (local dev).
- Self-host: `docker run -p 4040:4040 grafana/pyroscope`.

## Config (env via zod)

Add an `observability` section to `src/config/config.ts`:

```ts
const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  LOG_LEVEL: z.enum(['fatal', 'error', 'warn', 'info', 'debug', 'trace']).default('info'),
  OTEL_SERVICE_NAME: z.string().default('my-service'),
  OTEL_EXPORTER_OTLP_ENDPOINT: z.string().url().optional(), // unset = no export
  PYROSCOPE_SERVER: z.string().url().optional(), // unset = no profiling
  PYROSCOPE_AUTH_TOKEN: z.string().optional(),
})
```

## Wiring in `src/observability/index.ts` / the catch-all function

```ts
// api/[[route]].ts
import { handle } from 'hono/vercel'
import { startTelemetry } from '../src/observability/tracer'
import { startProfiling, stopProfiling } from '../src/observability/profiling'
import { createApp } from '../src/app'

const sdk = startTelemetry() // no-op when endpoint unset
startProfiling()             // no-op when server unset

export default async (req: Request) => {
  try {
    return await handle(createApp())(req)
  } finally {
    await sdk?.shutdown()
    await stopProfiling()
  }
}
```

## Key Dependencies

- `pino` — structured logging
- `@opentelemetry/sdk-node` + `@opentelemetry/api` — traces & metrics
- `@opentelemetry/exporter-trace-otlp-http` / `exporter-metrics-otlp-http` — OTLP export
- `@hono/otel` (Hono's OTel middleware) — inbound request spans
- `@opentelemetry/instrumentation-http` / `instrumentation-undici` /
  `instrumentation-pg` — outbound spans
- `@pyroscope/nodejs` — continuous profiling

## Verification

- `npm run build` (tsc) passes with the instrumentation imports wired.
- No `otel`, `pino`, `pyroscope` imports inside `core/`, `service/`, or DTO
  mappers — observability lives in `observability/` and middleware/wrappers
  only.
- Local/test runs (`OTEL_EXPORTER_OTLP_ENDPOINT` / `PYROSCOPE_SERVER` unset)
  emit logs but skip export — no crash, no hanging export retries.
- Traces carry `trace_id`/`span_id`; check spans appear in Vercel Observability
  or the configured collector after a request.
- No Prometheus scrape target is exposed on the public API path — metrics are
  pushed via OTLP only.
