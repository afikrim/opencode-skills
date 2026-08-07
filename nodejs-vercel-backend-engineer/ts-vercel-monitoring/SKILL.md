---
name: ts-vercel-monitoring
description: Add observability to TypeScript services deployed on Vercel as serverless Functions. Covers Vercel Observability (first-party OpenTelemetry ingestion), push-based OTLP export (no long-lived ports to scrape), pino structured logging, and Pyroscope continuous profiling. Builds on the generic ts-monitoring skill, replacing the long-running-server assumptions (pull Prometheus port, persistent process) with Vercel's serverless reality. Use when the user asks to set up logging, tracing, metrics, or profiling in a Hono/Vercel TypeScript service, enable Vercel Observability, or export OTel traces from Vercel Functions. Triggers on "vercel observability", "otel on vercel", "push-based monitoring", "hono monitoring", "pyroscope vercel".
---

# Monitoring & Observability on Vercel (TypeScript)

This skill is the **Vercel layer** on top of the generic `ts-monitoring`
skill. Read that skill first for the baseline instrumentations (pino logging,
`@opentelemetry/sdk-node`, OTel metric readers, Pyroscope agent, wiring
pattern). This skill only adjusts for **Vercel's serverless reality**.

## Vercel serverless reality check

- **Vercel Functions are ephemeral**: no persistent process, no port to
  scrape, no long-lived metrics endpoint. A pull-style Prometheus `/metrics`
  port or a debug/profiling port does **not** work.
- Observability must be **push-based**: emit traces/metrics over **OTLP** to a
  collector — Vercel's own Observability ingestion or a third-party backend.
- The same code runs in `vercel dev` locally and on Vercel. Guard config so
  local/test runs either skip export or export to a local collector.

## 1. Vercel Observability (first-party)

Vercel ships first-party OpenTelemetry ingestion for Functions:

- Enable in the Vercel dashboard: **Project → Observability** (or
  `enableRequestTracing`). Vercel then instruments the Function wrapper itself
  and captures request traces for every invocation.
- Optionally integrate a third-party backend (Datadog, Grafana Cloud, Axiom,
  etc.) via Vercel's Observability → OTLP forwarding settings, so the same
  traces flow to your tooling.
- The `@hono/otel` middleware (`import { otel } from 'hono/otel'`) gives
  per-request spans inside your app and composes with Vercel's own
  instrumentation.
- Set `service.name` (via resource attributes or `OTEL_SERVICE_NAME`) so traces
  group correctly in the dashboard.

## 2. OTLP export (push, not pull)

Use the generic skill's `startTelemetry()` but make export conditional and
non-blocking — a request must not hang because the collector is slow:

```ts
// src/observability/tracer.ts
import { NodeSDK } from '@opentelemetry/sdk-node'
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http'

export function startTelemetry() {
  if (!process.env.OTEL_EXPORTER_OTLP_ENDPOINT) return // local/test: no export

  const sdk = new NodeSDK({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME ?? 'my-service',
    }),
    traceExporter: new OTLPTraceExporter({
      concurrencyLimit: 2,
      timeoutMillis: 2000, // never block the response
    }),
  })
  sdk.start()
  return sdk
}
```

- Keep exporters fire-and-forget; a slow collector must not stall the Function
  (you still pay for invocation time).
- Shut down best-effort before the handler returns so spans flush:
  `await sdk?.shutdown()` in a `finally`.

## 3. Metrics: push via OTLP, no scrape target

- No local `/metrics` endpoint. Register meters and let the periodic OTLP
  metric reader push samples (see the generic skill's `metrics.ts`).
- On Vercel, emission is best-effort per invocation; design dashboards for
  sampled/aggregated data rather than per-request exactness.
- For Prometheus-style backends, point the OTLP metric exporter at an
  OpenTelemetry Collector that translates OTLP → Prometheus (e.g. Grafana
  Cloud or a self-hosted collector). There is no direct scrape target on
  Vercel.

## 4. Profiling (Pyroscope)

Same as the generic skill's Pyroscope agent, but bounded to the invocation
lifetime. Start on module load, stop before the handler returns:

```ts
// api/[[route]].ts
import { handle } from 'hono/vercel'
import { createApp } from '../src/app'
import { startTelemetry } from '../src/observability/tracer'
import { startProfiling, stopProfiling } from '../src/observability/profiling'

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

- `@pyroscope/nodejs` samples during the invocation and pushes to the server;
  `stopProfiling()` before returning flushes the profile.
- Skip entirely when `PYROSCOPE_SERVER` is unset (local dev).
- There is no pprof-style on-demand CPU profile on Vercel — use Pyroscope for
  continuous flame graphs instead.

## Environment / config

Use zod config (generic skill) with `VERCEL` (Vercel sets this env flag) to
adjust behavior per environment:

```ts
const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  VERCEL: z.literal('1').optional(), // set by Vercel in production
  LOG_LEVEL: z.enum(['fatal', 'error', 'warn', 'info', 'debug', 'trace']).default('info'),
  OTEL_SERVICE_NAME: z.string().default('my-service'),
  OTEL_EXPORTER_OTLP_ENDPOINT: z.string().url().optional(),
  PYROSCOPE_SERVER: z.string().url().optional(),
})
```

## Verification

- `npm run build` (tsc) passes.
- `npx vercel dev` runs locally; local runs (endpoint/server unset) emit logs
  but skip export — no crash, no hanging export retries.
- After a request in Vercel Observability: spans carry `trace_id`/`span_id`;
  check the dashboard (or forwarded backend) for the invocation trace.
- No Prometheus scrape target is exposed on any public path — metrics are
  pushed via OTLP only.
- No `otel`, `pino`, `pyroscope` imports inside `core/`, `service/`, or DTO
  mappers — observability lives in `observability/` and middleware/wrappers
  only.
