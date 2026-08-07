---
name: grafana
description: Set up and configure Grafana locally, including a full observability stack (Grafana + Prometheus + Loki + Tempo + Pyroscope) via docker compose, provisioning datasources/dashboards, and connecting an OTel-instrumented Go service. Use when the user asks to configure Grafana locally, run Grafana with docker compose, provision datasources or dashboards, or stand up a local observability stack. Triggers on "grafana", "observability stack", "grafana docker", "provisioning grafana", "grafana loki tempo prometheus pyroscope".
---

# Grafana (Local Setup)

Grafana is the visualization/alerting frontend for the observability pillars
(set up in the `monitoring` skill). This skill covers standing it up locally,
provisioning datasources/dashboards as code, and connecting a Go service.

## Prefer docker compose

**Use docker compose** for local Grafana — it is the recommended, reproducible
way and matches how the whole observability stack is run. A single
`compose.yaml` brings up every backend (Prometheus, Loki, Tempo, Pyroscope)
plus Grafana. Prefer `docker compose` over:

- `docker run` one-offs — manual, no config as code, no service network.
- Installing binaries natively — version drift, no isolation, harder cleanup.
- Kubernetes (k3s/kind) — overkill for local dev.

Only go native/binary if you specifically need no-Docker at all.

## Option A: Grafana alone (smallest)

```yaml
# compose.yaml
services:
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=http://localhost:3000
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
volumes:
  grafana-data:
```

```sh
docker compose up -d
# open http://localhost:3000  (admin / admin)
```

## Option B: Full local observability stack (recommended for the monitoring skill)

One compose file with all backends the Go service sends telemetry to. The OTel
Collector ingests OTLP from the service and routes traces→Tempo, metrics→
Prometheus, logs→Loki. Profiles→Pyroscope. Grafana provisions all datasources.

```yaml
# compose.yaml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel/config.yaml"]
    volumes:
      - ./otel/config.yaml:/etc/otel/config.yaml
    ports:
      - "4317:4317" # OTLP gRPC (app → collector)

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yaml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus

  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    command: ["-config.file=/etc/loki/local-config.yaml"]

  tempo:
    image: grafana/tempo:latest
    ports:
      - "3200:3200"
    command: ["-config.file=/etc/tempo/local-config.yaml"]

  pyroscope:
    image: grafana/pyroscope:latest
    ports:
      - "4040:4040"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - grafana-data:/var/lib/grafana
    depends_on:
      - prometheus
      - loki
      - tempo
      - pyroscope

volumes:
  prometheus-data:
  grafana-data:
```

### Supporting config files

`otel/config.yaml` (route OTLP to backends):

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
processors: []
exporters:
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true
  prometheus:
    endpoint: "0.0.0.0:8889"
  otlphttp/loki:
    endpoint: http://loki:3100/otlp
service:
  pipelines:
    traces:   { receivers: [otlp], exporters: [otlp/tempo] }
    metrics:  { receivers: [otlp], exporters: [prometheus] }
    logs:     { receivers: [otlp], exporters: [otlphttp/loki] }
```

`prometheus.yaml`:

```yaml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: "otel-collector"
    static_configs:
      - targets: ["otel-collector:8889"]
  - job_name: "go-service"
    static_configs:
      - targets: ["host.docker.internal:9090"] # app /metrics port
```

`tempo` config — use the single-binary local storage config from the official
Tempo docker-compose example (`-config.file` pointing at `local-config.yaml`
with `storage.trace.backend: local`).

### Provision Grafana datasources (as code)

Datasources are auto-provisioned from YAML — no manual clicking. Provisioning
directory is mounted above at `./grafana/provisioning`.

```yaml
# grafana/provisioning/datasources/datasources.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
  - name: Pyroscope
    type: grafana-pyroscope-datasource
    access: proxy
    url: http://pyroscope:4040
```

### Provision dashboards (as code)

```yaml
# grafana/provisioning/dashboards/dashboards.yml
apiVersion: 1
providers:
  - name: "default"
    orgId: 1
    folder: ""
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
```

Drop exported dashboard JSON into `grafana/provisioning/dashboards/`. They load
automatically; changes hot-reload within `updateIntervalSeconds`.

## Config key points

- Credentials: set `GF_SECURITY_ADMIN_PASSWORD` in the compose environment.
  Defaults are `admin/admin` — never leave it in anything shared.
- Provisioned datasources/dashboards are **read-only in the UI** — edit the
  YAML/JSON and restart, not the UI. Clone in the UI if you must tweak.
- Grafana config is via `GF_*` env vars, not a config file, when running the
  official image. Common ones: `GF_SERVER_ROOT_URL`, `GF_USERS_ALLOW_SIGN_UP`,
  `GF_AUTH_ANONYMOUS_ENABLED`.
- Keep the data volumes (`grafana-data`, `prometheus-data`) so state survives
  `docker compose down` (not `down -v`, which deletes volumes).

## Connecting the Go service (from the `monitoring` skill)

```sh
export OTLP_ENDPOINT=localhost:4317   # → otel-collector
export METRICS_PORT=9090              # app /metrics, scraped by prometheus
export PYROSCOPE_SERVER=http://localhost:4040
```

Then `docker compose up -d`, run the app, and check:

1. `http://localhost:3000` → Connections → Data sources → all green.
2. Explore → Prometheus → `http_requests_total` present.
3. Explore → Tempo → search by service name → spans visible.
4. Explore → Loki → logs with `trace_id` present.
5. Explore → Pyroscope → flame graphs from the app.

## Importing community dashboards

Dashboards → Import → enter ID → pick the Prometheus datasource. Handy IDs:
Node Exporter Full (1860), Docker monitoring (193), Loki (13639).

## Troubleshooting

- **"Data source not found" / stale UIDs**: provisioned sources with explicit
  UIDs can conflict with old rows in `grafana-data`. Fix: wipe the volume
  (`docker compose down -v`).
- **Tempo "trace not found"**: disable time-shift on the Tempo datasource
  (`traceQuery.timeShiftEnabled: false`) so trace-by-id searches carry no time
  bounds.
- **No metrics in Prometheus**: check `http://localhost:9090/targets` — the
  Go service target must be `UP`.
- **Loki rejects OTLP logs**: use the OTLP endpoint `loki:3100/otlp` in the
  collector, not raw pushes.
- **Port conflicts**: `4317`, `9090`, `3200`, `4040`, `3100` must be free on
  the host.

## Verification

- `docker compose up -d` starts all services; `docker compose ps` shows healthy.
- Datasources appear pre-configured without manual UI steps.
- Point the instrumented Go service at the collector and confirm data lands in
  each Explore tab.
