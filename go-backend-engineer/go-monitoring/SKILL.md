---
name: go-monitoring
description: Add observability to Go services: structured logging with zap, OpenTelemetry (traces/metrics/logs with OTLP export), Prometheus metrics on a separate port, and profiling with pprof + Pyroscope continuous profiling. Use when the user asks to set up logging, tracing, metrics, or profiling in a Go service, or integrate zap, OpenTelemetry, Prometheus, pprof, or Pyroscope. Triggers on "monitoring", "observability", "structured logging", "open telemetry", "metrics", "profiling", "pyroscope", "zap", "prometheus".
---

# Monitoring & Observability (Go)

Instrument a Go service with four pillars, aligned with the hexagonal
architecture layout so observability stays in wrappers and never leaks into
business logic:

1. **Structured logging** — zap
2. **Tracing** — OpenTelemetry (OTLP export)
3. **Metrics** — Prometheus (separate port)
4. **Profiling** — pprof + Pyroscope continuous profiling

## Directory Layout

```text
internal/
├── observability/
│   ├── config.go        # builds zap logger + otel sdk providers (one init)
│   ├── logger.go        # zap setup + otelzap wrapper (trace correlation)
│   ├── tracing.go       # tracer provider, OTLP exporter, resource
│   ├── metrics.go       # prometheus registry + RED middleware
│   └── profiling.go     # pprof debug server + pyroscope agent
```

## 1. Structured Logging (zap)

Use `go.uber.org/zap` with JSON encoding. Level comes from env
(`LOG_LEVEL`), production config uses `zap.NewProduction()`-style JSON output.

```go
// internal/observability/logger.go
package observability

import (
    "go.uber.org/zap"
    "go.uber.org/zap/zapcore"

    "github.com/uptrace/opentelemetry-go-extra/otelzap"
)

func NewLogger(level string) (*otelzap.Logger, error) {
    var lvl zapcore.Level
    if err := lvl.UnmarshalText([]byte(level)); err != nil {
        return nil, err
    }

    cfg := zap.NewProductionConfig()
    cfg.Level = zap.NewAtomicLevelAt(lvl)
    cfg.EncoderConfig.TimeKey = "timestamp"
    cfg.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder

    base, err := cfg.Build()
    if err != nil {
        return nil, err
    }

    return otelzap.New(base), nil // adds trace_id/span_id correlation
}
```

Rules:

- Use the **typed API** (`zap.String`, `zap.Int`, `zap.Error`) — zero-allocation
  and catches type errors at build time.
- Use `log.Ctx(ctx)` everywhere so logs carry `trace_id`/`span_id` from the
  active OpenTelemetry span.
- Inject `*otelzap.Logger` into services/handlers as a constructor dependency
  (same DI pattern as the architecture skill) — no global logger in business
  logic.
- Never log secrets, tokens, or full PII. Redact fields with `zap.Skip()` or a
  sanitizing encoder when needed.
- Keep field names consistent (`user_id`, not `userID`/`userId`).

## 2. OpenTelemetry Tracing

Set up a `TracerProvider` with an OTLP exporter, resource attributes
(`service.name`, `service.version`), and a batch span processor. Use OTLP
exporters so the same pipeline works with Jaeger, Grafana, Uptrace, Datadog,
etc.

```go
// internal/observability/tracing.go
package observability

import (
    "context"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
)

func NewTracerProvider(ctx context.Context, endpoint, service, version string) (*sdktrace.TracerProvider, error) {
    exporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint(endpoint),
        otlptracegrpc.WithInsecure(), // use TLS in prod or configure accordingly
    )
    if err != nil {
        return nil, err
    }

    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName(service),
            semconv.ServiceVersion(version),
        )),
    )
    otel.SetTracerProvider(tp)
    return tp, nil
}
```

### Auto-instrumentation via contrib

Keep adapters/handlers thin — instrumentation goes in wrappers, not business
code:

- **DB**: wrap `*sql.DB` with `github.com/uptrace/opentelemetry-go-extra/otelsql`
  to get spans + DB query metrics automatically:

  ```go
  db, err := otelsql.Open("postgres", dsn, otelsql.WithSpanOptions(otelsql.ReportDBStats()))
  ```

- **HTTP handlers**: wrap the router/mux with `otelhttp.NewHandler` (from
  `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp`) to get spans
  per request with `http.method`, `http.route`, `http.status_code`.
- **Outbound HTTP (adapters calling external APIs)**: wrap the client transport
  with `otelhttp.NewTransport` so external calls appear in the trace.
- **Redis**: use `go-redis` otel instrumentation hooks if the adapter uses
  go-redis.

Pattern: instrumentation lives in the **adapter/handler constructor or
middleware**, so service and core stay 100% clean of otel imports.

## 3. Metrics (Prometheus)

Metrics endpoint **in the same process, on a separate port**. Never on the
public API port. Scrape with Prometheus; RED-method HTTP metrics (Rate, Errors,
Duration) plus Go runtime metrics come free via the default registry.

```go
// internal/observability/metrics.go
package observability

import (
    "net/http"

    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

func NewMetricsServer() *http.Server {
    mux := http.NewServeMux()
    mux.Handle("/metrics", promhttp.Handler())

    return &http.Server{Addr: ":9090", Handler: mux} // separate port
}
```

HTTP RED middleware (handler-level; wrap the router in `main.go`):

```go
httpRequests := prometheus.NewCounterVec(
    prometheus.CounterOpts{Name: "http_requests_total", Help: "Total HTTP requests"},
    []string{"method", "code"},
)
httpDuration := prometheus.NewHistogramVec(
    prometheus.HistogramOpts{
        Name:    "http_request_duration_seconds",
        Help:    "Request latency",
        Buckets: prometheus.DefBuckets,
    },
    []string{"method"},
)
prometheus.MustRegister(httpRequests, httpDuration)

var instrumented = promhttp.InstrumentHandlerDuration(
    httpDuration,
    promhttp.InstrumentHandlerCounter(httpRequests, router),
)
```

Service/adapter-level metrics (when useful): counters for processed jobs,
histograms for DB latency, gauges for queue depth. Register them once in
`main.go` and expose them via the same `/metrics` port. Keep label cardinality
bounded — never put user IDs, emails, or free-form strings in labels.

## 4. Profiling

### On-demand: pprof (stdio)

Serve pprof on a **separate debug port** bound to localhost — never publicly.

```go
// internal/observability/profiling.go
package observability

import (
    "net/http"
    "net/http/pprof"
)

func NewPprofServer() *http.Server {
    mux := http.NewServeMux()
    mux.HandleFunc("/debug/pprof/", pprof.Index)
    mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
    mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
    mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
    mux.HandleFunc("/debug/pprof/trace", pprof.Trace)

    return &http.Server{Addr: "localhost:6060", Handler: mux}
}
```

Capture and analyze:

```sh
go tool pprof -http=:8888 http://localhost:6060/debug/pprof/heap
curl -o cpu.prof 'http://localhost:6060/debug/pprof/profile?seconds=30'
go tool pprof -base before.prof after.prof   # diff profiles
```

Enable block/mutex profiling **only while investigating** (overhead 5–20%):
`runtime.SetBlockProfileRate(1)`, `runtime.SetMutexProfileFraction(1)`.

### Continuous: Pyroscope

Push CPU/memory/mutex profiles to a Pyroscope server (self-hosted via Docker or
Grafana Cloud) for always-on flame graphs.

```go
pyroscope.Start(pyroscope.Config{
    ApplicationName: "my-service{env=production,version=1.0.0}",
    ServerAddress:   os.Getenv("PYROSCOPE_SERVER"), // e.g. http://localhost:4040
    Logger:          pyroscope.StandardLogger,
    UploadRate:      10 * time.Second,
    ProfileTypes: []pyroscope.ProfileType{
        pyroscope.ProfileCPU,
        pyroscope.ProfileInuseSpace,
        pyroscope.ProfileAllocSpace,
        pyroscope.ProfileMutexCount,
    },
})
```

- Skip Pyroscope when `PYROSCOPE_SERVER` is unset (local dev).
- Tag with `pyroscope.Labels("endpoint", path)` around hot handlers to slice
  profiles by endpoint.
- Self-host: `docker run -p 4040:4040 grafana/pyroscope`.

## Config (env via caarlos0/env)

Add an `Observability` section to `internal/config/config.go`:

```go
Observability struct {
    LogLevel       string `env:"LOG_LEVEL" envDefault:"info"`
    OTLPEndpoint   string `env:"OTLP_ENDPOINT"`
    MetricsPort    string `env:"METRICS_PORT" envDefault:"9090"`
    PprofPort      string `env:"PPROF_PORT" envDefault:"6060"`
    PyroscopeServer string `env:"PYROSCOPE_SERVER"`
} `envPrefix:"OBS_"`
```

## Wiring in `cmd/<program>/main.go`

```go
func main() {
    cfg, err := config.Load()
    if err != nil { log.Fatal(err) }

    logger, err := observability.NewLogger(cfg.Observability.LogLevel)
    if err != nil { log.Fatal(err) }
    defer logger.Sync()

    ctx := context.Background()
    tp, err := observability.NewTracerProvider(ctx, cfg.Observability.OTLPEndpoint, "my-service", "1.0.0")
    if err != nil { log.Fatal(err) }
    defer func() { _ = tp.Shutdown(ctx) }()

    go func() { _ = observability.NewMetricsServer().ListenAndServe() }() // :9090
    go func() { _ = observability.NewPprofServer().ListenAndServe() }()   // localhost:6060

    if cfg.Observability.PyroscopeServer != "" {
        observability.StartPyroscope(cfg.Observability.PyroscopeServer)
    }

    // ... build adapters (db via otelsql.Open), services, handlers,
    // wrap router with otelhttp + metrics middleware, start server
}
```

## Key Dependencies

- `go.uber.org/zap` — structured logging
- `github.com/uptrace/opentelemetry-go-extra/otelzap` — trace correlation
- `github.com/uptrace/opentelemetry-go-extra/otelsql` — DB spans/metrics
- `go.opentelemetry.io/otel` + `go.opentelemetry.io/otel/exporters/otlp/...`
- `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp` — handler/transport instrumentation
- `github.com/prometheus/client_golang/prometheus` + `promhttp`
- `github.com/grafana/pyroscope-go` — continuous profiling

## Verification

- `go build ./...` passes with the instrumentation imports wired.
- No `otel`, `zap`, `prometheus`, or `pyroscope` imports inside `core/`,
  `service/`, or DTO mappers — observability lives in `observability/` and
  adapter/handler wrappers only.
- Logs show `trace_id`/`span_id` when a trace is active.
- `/metrics` and `/debug/pprof/` are not reachable on the public API port.
