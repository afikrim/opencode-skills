---
name: nextjs-monitoring
description: Add observability and performance monitoring to a Next.js (App Router) application: Web Vitals reporting via useReportWebVitals (manual or Vercel Analytics), OpenTelemetry for server-side tracing in Route Handlers and Server Components, error tracking, and structured logging. Includes the Vercel-specific differences (serverless, no long-lived ports) and how to report Core Web Vitals (FCP, LCP, CLS, INP, TTFB) to analytics. Use when the user asks to measure performance in Next.js, report Web Vitals, set up Vercel Analytics or OpenTelemetry for Next.js, or monitor a Next.js app. Triggers on "web vitals", "vercel analytics", "nextjs observability", "opentelemetry nextjs", "core web vitals", "lcp", "inp", "performance monitoring nextjs".
---

# Monitoring & Observability (Next.js)

Three things to observe in a Next.js app:

1. **Performance (client)** — Core Web Vitals from the browser.
2. **Tracing (server)** — OpenTelemetry spans for Route Handlers, Server
   Components, Server Actions.
3. **Errors & logs** — client error boundaries + server logging.

## Vercel serverless reality (applies to server-side parts)

- Route Handlers and RSC run as **serverless functions**: no persistent
  process, no port to scrape, no long-lived metrics endpoint.
- Server-side observability must be **push-based** via OTLP (Vercel
  Observability or a collector). Client-side performance is reported from the
  browser via `useReportWebVitals` / Vercel Analytics.

## 1. Web Vitals (client performance)

Next.js exposes `useReportWebVitals` from `next/web-vitals`, called on the
client with each metric (TTFB, FCP, LCP, CLS, FID→INP).

```tsx
'use client'

import { useReportWebVitals } from 'next/web-vitals'

export function WebVitals() {
  useReportWebVitals((metric) => {
    // Send to your analytics/beacon
    const body = JSON.stringify(metric)
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/analytics', body)
    } else {
      fetch('/api/analytics', { body, method: 'POST', keepalive: true })
    }
  })
  return null
}
```

Mount it in the root layout:

```tsx
import { WebVitals } from '@/components/web-vitals'

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <WebVitals />
      </body>
    </html>
  )
}
```

### Vercel Analytics (managed)

The zero-code path: install `@vercel/analytics` and add the script to the
root layout. Vercel then collects Web Vitals and page views automatically
(dashboard: **Analytics → Web Analytics / Speed Insights**).

```bash
npm i @vercel/analytics
```

```tsx
import { Analytics } from '@vercel/analytics/react'

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  )
}
```

Rules:

- `useReportWebVitals` for **manual/self-hosted** reporting (your own
  endpoint/GA); `@vercel/analytics` for the managed dashboard. Pick one
  primary path to avoid double counting.
- CLS must be rounded (integers for analytics platforms):
  `Math.round(metric.value * 1000)` for CLS, plain round otherwise.
- Metric `id` is unique per page load — use it as the event label.
- Don't block rendering: both approaches are async/non-blocking by design.

## 2. Server-side tracing (OpenTelemetry)

Instrument server-side code so Route Handlers, Server Components, and Server
Actions produce spans, exported via OTLP.

```bash
npm i @opentelemetry/sdk-node @opentelemetry/api \
  @opentelemetry/exporter-trace-otlp-http \
  @opentelemetry/instrumentation-http \
  @opentelemetry/instrumentation-fetch
```

Next.js officially supports OpenTelemetry instrumentation via
`instrumentation.ts` at the project root:

```ts
// instrumentation.ts
import { NodeSDK } from '@opentelemetry/sdk-node'
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http'
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node'

export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const sdk = new NodeSDK({
      traceExporter: new OTLPTraceExporter({
        url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT,
        timeoutMillis: 2000,
      }),
      instrumentations: [getNodeAutoInstrumentations()],
      serviceName: 'my-next-app',
    })
    sdk.start()
  }
}
```

- Skip the Node SDK on the edge runtime (`NEXT_RUNTIME !== 'nodejs'`).
- Set `service.name` via resource or env (`OTEL_SERVICE_NAME`) so traces group
  correctly.
- On Vercel, **Vercel Observability** provides first-party ingestion of these
  OTLP spans (enable in the dashboard; optionally forward to Datadog/Grafana
  etc.). Locally, point OTLP at a local collector or skip export when unset.
- Keep exporters fire-and-forget with short timeouts — a slow collector must
  not stall a page render.

For fine-grained spans inside a Server Action or Route Handler, use the API:

```ts
import { trace } from '@opentelemetry/api'

const tracer = trace.getTracer('my-next-app')

export async function POST(request: Request) {
  return await tracer.startActiveSpan('process-payment', async (span) => {
    try {
      // ...
      return Response.json({ ok: true })
    } finally {
      span.end()
    }
  })
}
```

## 3. Errors & logs

- **Client errors**: wrap pages/segments with `error.tsx` (catches client
  errors + server errors during streaming) and `global-error.tsx` for the root.
  Report inside the boundary to your error tracker:
  `reportError(error)` from a client component, or the error tracker SDK.
- **Server errors**: Route Handlers return error responses with
  `try/catch` — never leak internals. Log via pino (see `ts-monitoring`) with
  request context, never secrets.
- **Logs on Vercel**: Function logs are visible in the dashboard; structured
  JSON logs (`pino`) are parseable and linkable to traces via
  `trace_id`/`span_id`.

```tsx
'use client'

export default function ErrorBoundary({ error, reset }: {
  error: Error
  reset: () => void
}) {
  // report to Sentry / Datadog / etc.
  return (
    <div>
      <h1>Something went wrong</h1>
      <button onClick={reset}>Retry</button>
    </div>
  )
}
```

## Config (env via zod)

Add an `observability` section to your env schema (extend the
`ts-monitoring`/`ts-vercel-monitoring` conventions):

```ts
const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  VERCEL: z.literal('1').optional(),
  OTEL_SERVICE_NAME: z.string().default('my-next-app'),
  OTEL_EXPORTER_OTLP_ENDPOINT: z.string().url().optional(), // unset = no export
  LOG_LEVEL: z.enum(['fatal', 'error', 'warn', 'info', 'debug', 'trace']).default('info'),
})
```

## Verification

- `npm run build` passes with instrumentation wired.
- Web Vitals appear in your analytics (manual beacon or Vercel Analytics) after
  a few page loads.
- Server traces show up in Vercel Observability (or configured collector);
  spans for Route Handlers/Server Actions are visible with `service.name`.
- Local runs with OTLP unset skip export — no crash, no hanging render.
- Client errors land in the error tracker; server errors are logged without
  leaking internals.
- No `@opentelemetry`/pino imports inside leaf client components that would
  bloat the client bundle.
