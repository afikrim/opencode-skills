---
name: figjam-system-design
description: Render Aziz's system design boards in FigJam — deployment-boundary sections (AWS / NIAGAHOSTER / VPN) with nested layer subsections (FRONTEND / BACKEND / AUTO SCALING), SQUARE components, cylindrical ENG_QUEUE/ENG_DATABASE data stores, ELLIPSE annotations, left-to-right connector flow with ARROW_LINES caps and interaction labels, CI/CD lanes, per-scenario flowchart sections (ROUNDED_RECTANGLE steps, DIAMOND decisions, branch labels, loop-backs), and Database Table schema widgets with rationale stickies. Use when creating, laying out, or verifying a system design / infrastructure / architecture board in FigJam. Triggers on "figjam system design", "figjam infrastructure", "figjam architecture diagram", "draw the system design in figjam", "aws diagram figjam", "component diagram figjam".
---

# FigJam System Design Board (Aziz's standard)

Render the system design board (see `system-design-diagram`) in FigJam with a
strict visual language so every system board looks the same.

> **Related skills:** what the board contains → load `system-design-diagram`.
> Flowchart-lane conventions shared with product flows → `figjam-product-design-flow`.
> General FigJam shapes/connectors → figma skills (`figma-use-figjam`, `figma-use`).

## Shape → meaning mapping (fixed)

| FigJam shape | Meaning | Size (px) |
|---|---|---|
| `SQUARE` | Service / component (NGINX, WEB SERVER, LOAD BALANCER, USER, 3RD PARTIES, service boxes) | 208×208 |
| `ENG_QUEUE` | Data store / cache / queue (MONGODB, MYSQL, REDIS, DELIV BANK MONGODB, cache redis, aws sqs) | 256×208 |
| `ENG_DATABASE` | Database instance (depayment_prod, bank_prod, dlv, mariadb master/slave) | 208×208 or 256×208 |
| `ELLIPSE` | Annotation (payloads, review notes) | hug content |
| `ROUNDED_RECTANGLE` | Flow start / stop / step (Start, Login Page, End) | 256×208 |
| `DIAMOND` | Flow decision (Is Registered?, Is Retry > 3) | 256×208 |
| `STICKY` (CUSTOM) | Rationale / context note anchored to a component | 240×240 |
| `Database Table` widget | Real table schema (see Block 4) | 400 wide |

Components default to **white/neutral fill with dark text** — no per-type
color coding; meaning comes from shape, not hue.

## Board layout conventions

- **Boundary = section.** Name it by host: `AWS`, `NIAGAHOSTER`, `AWS
  CLOUD`, `VPN`. Nested **layer subsections** inside a boundary:
  `FRONTEND`, `BACKEND`, `AUTO SCALING`. Nesting: boundary → layer →
  components.
- **Left-to-right data flow.** `USER` far left → edge (CDN/NGINX/ALB) →
  service → data store on the right. `3RD PARTIES` far right when the system
  calls out. Keep lanes parallel; never cross connectors.
- **Fan-outs:** load balancer fans to each instance in `AUTO SCALING`; the
  write replica fans to read replicas (`Write data` / `Read data` labels).
- **CI/CD lane:** horizontal row `SOURCE (GITHUB)` → `AWS CODEPIPELINE` →
  `AWS CODEBUILD` → `AWS CODEDEPLOY` → `AWS ECS` (one per target), each hop
  labeled `Pull Source` / `Build artifact` / `Deploy artifact`.
- **Flowchart sections:** one section per scenario (`Not Logged In Flow`,
  `Normal Logged Flow`). Left-to-right steps, branches to lanes above/below,
  and loop-backs to a prior node.
- **Keep old vs new visible:** document a migration by drawing two
  `NIAGAHOSTER` sections (old Express service, new NestJS service) and
  annotate the difference with a sticky.

## Connector conventions

```js
function link(from, to, label) {
  const c = figma.createConnector();
  c.connectorStart = { nodeId: from.id, magnet: 'AUTO' };
  c.connectorEnd   = { nodeId: to.id,   magnet: 'AUTO' };
  c.connectorStartCap = 'NONE';          // square end (source)
  c.connectorEndCap   = 'ARROW_LINES';   // arrow (target)
  if (label) { c.text = label; }         // interaction / branch label
  return c;
}
```

Labels are always present and describe what crosses the edge:

- Interactions: `createTransaction getTransaction`, `formated callback`,
  `callback`, `create new user`, `Pull Source`.
- Data semantics: `Write data`, `Read data`.
- Flow branches: `Registered` / `Not Registered`, `Correct` / `Incorrect`,
  `Retry`, `Email exists`, `Password not pass regexp`, `Redirected`.

## Sticky note semantics

- **CUSTOM-color stickies** = rationale/design notes anchored near the
  component or table they explain ("MongoDB use to store session...",
  "Better to use docker in our backend app...", "We must specified every
  endpoint that will be exposed to the public").
- **STICKY_GRAY** = neutral flow context ("Auth menggunakan token validasi
  PIN").
- **STICKY_RED** = important warning/caveat ("Ngasi token panjang, disimpan
  sma FE", "FE ngirim token panjang, OTP, dan PIN baru").
- Anchor: place the sticky 20–40px off the node it annotates, never in the
  middle of a connector lane.

## Schema block (Database Table)

Use the FigJam **Database Table** widget (Add → Widgets), one per real table:

- Header = table name (snake_case: `deposit`, `accounts`, `transactions`,
  `memberships`, `services`, `products`, `user_token`).
- Rows = column rows: optional key marker (`key`/`snowflake`/`Text`/`link`
  icon), column name, and type (`bigint`, `int`, `varchar`, `enum`,
  `boolean`, `timestamp`, `longtext`, `serial`).
- Nullable → `?` suffix on the type (`int?`, `varchar?`, `timestamp?`).
- New columns get a **`NEW!!`** badge.
- Draw connectors between related tables (e.g. `transactions` → `accounts`).

If the widget is unavailable, reproduce its structure with a frame: 48px
header row (table name) + 48px column rows (`name` | `type`), 400 wide.

## FigJam API recipes

```js
const h = (r, g, b) => ({ r: r / 255, g: g / 255, b: b / 255, a: 1 });

// Component / data store / annotation
const svc = figma.createShapeWithText('SQUARE');     // 'ENG_QUEUE' | 'ENG_DATABASE' | 'ELLIPSE'
svc.text = 'NGINX';
svc.resize(208, 208);

// Section = deployment boundary; subSection = layer
function makeSection(name, x, y, children, pad = 40) {
  const s = figma.createSection();
  s.name = name;
  children.forEach((c) => { c.x += pad; c.y += pad; });
  s.appendChild(children[0]);
  // hug: compute extent from child bounds, set section x/y/size
  const minX = Math.min(...children.map((c) => c.x)), minY = Math.min(...children.map((c) => c.y));
  const maxX = Math.max(...children.map((c) => c.x + c.width));
  const maxY = Math.max(...children.map((c) => c.y + c.height));
  s.x = minX - pad; s.y = minY - pad;
  s.resize(maxX - minX + pad * 2, maxY - minY + pad * 2);
  return s;
}
```

Rules for sections: never auto-resize a section to cover two unrelated
boundaries; each boundary gets its own section. When verifying, a section's
content must fit inside with ≥ pad on every edge.

## Verification

- Every component sits inside exactly one boundary section; layers are
  nested subsections.
- Components are `SQUARE`; data stores/caches/queues are `ENG_QUEUE`;
  databases are `ENG_DATABASE`; annotations are `ELLIPSE`.
- Flow reads left→right, `USER` left, `3RD PARTIES` right when present; no
  crossing connectors.
- Every connector is labeled (interaction, `Write data`/`Read data`, or a
  branch condition) and ends with `ARROW_LINES`.
- AUTO SCALING fans from the load balancer; read replicas fan from the
  writer.
- Flowchart sections: `ROUNDED_RECTANGLE` steps, `DIAMOND` decisions, all
  branches labeled, loop-backs land on a real node.
- Tables use the Database Table widget (name header, key markers, types with
  `?` for nullable, `NEW!!` badges).
- Rationale stickies: CUSTOM=note, GRAY=context, RED=warning; each anchored
  to the node it explains.
- Colors come only from the `h()` helper (0–255 → 0–1 conversion).
