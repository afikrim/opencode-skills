---
name: system-design-diagram
description: Build a system design board the way Aziz does — a deployment-and-component diagram plus supporting flowcharts, DB schema, and rationale notes. Covers the fixed notation (boundary sections for hosts like AWS/NIAGAHOSTER/VPN, nested layer subsections like FRONTEND/BACKEND/AUTO SCALING, SQUARE components, cylindrical data stores, labeled connectors describing the interaction, left-to-right USER→…→3RD PARTY flow, CI/CD lanes, and Start/Stop+DIAMOND flowchart lanes for scenarios). Use when the user asks to design a system, sketch infrastructure/architecture/topology, plan services and data stores, show how components interact, or spec a backend deployment. Triggers on "system design", "infrastructure diagram", "architecture diagram", "component diagram", "topology", "deployment", "design the system", "aws diagram", "how should the backend look".
---

# System Design Board (Aziz's standard)

A system design board is one canvas with **four blocks**, mirroring how the
Deliv and reference system-design boards are drawn:

1. **Context** — actors (USER, 3RD PARTIES) and the top-level flow.
2. **Infrastructure / component diagram** — every service, data store, and
   host, grouped by deployment boundary, with connectors labeled by the
   interaction they carry.
3. **Supporting lanes** — CI/CD pipeline, and per-scenario **flowcharts**
   (login, reset, checkout) as separate sections.
4. **Schema + rationale** — `Database Table` widgets for real tables, and
   sticky notes capturing why each decision was made.

> **Related skills:** rendering this board in FigJam → load
> `figjam-system-design`. What the flowchart lanes look like is shared with
> product flows → `product-design-flow` for the user-journey variant. This
> skill defines *what* a system design board contains and its notation.

## Block 1 — Context (actors and entry points)

- Start from the actor on the left: `USER` (and `3RD PARTIES` on the far
  right when the system calls out).
- The user connects to the edge first: CDN / NGINX / proxy / load balancer.
- Keep one arrow per relationship; never cross connectors between lanes.

## Block 2 — Infrastructure / component diagram

The core block. Rules from the reference boards:

**Deployment boundaries are sections.** Name them by host / environment:
`AWS`, `NIAGAHOSTER`, `AWS CLOUD`, `VPN`. Everything that runs in that
environment lives inside its section.

**Logical layers are nested subsections** inside a boundary: `FRONTEND`,
`BACKEND`, `AUTO SCALING`. Nesting reads: boundary → layer → components.

**Component notation (fixed):**

| Element | Shape | Examples from the boards |
|---|---|---|
| Service / component | `SQUARE` | NGINX, WEB SERVER, LOAD BALANCER, DELIV BANK SERVICE, CDN, AWS S3 |
| Data store / cache / queue | `ENG_QUEUE` (cylindrical) | MONGODB, MYSQL, REDIS, DELIV BANK MONGODB, cache redis, aws sqs |
| Database instance | `ENG_DATABASE` | depayment_prod, bank_prod, dlv, mariadb master/slave |
| Annotation | `ELLIPSE` | "Payload: Cart, current PIN", "R: Jadiin 1, buat modul nnti bikin dibawahnya" |
| In-flow step / page | `ROUNDED_RECTANGLE` | Login Page, Send Reset Password Email, Home Page (see Block 3) |

**Data flow is left→right:** `USER` → edge (CDN/NGINX/ALB) → service →
data store. Multiple web-server instances sit in an `AUTO SCALING`
subsection, fanned from the load balancer; replicas (write + read) fan from
the writer.

**Connectors** are arrow lines. Label every connector with what it carries:

- API / interaction: `createTransaction getTransaction`, `formated
  callback`, `callback`, `create new user`.
- Data semantics: `Write data`, `Read data` (between app and DB replicas).
- CI/CD: `Pull Source`, `Build artifact`, `Deploy artifact`.

Labels sit on the line; single-line short phrases only.

**When things change over time**, show old vs new: a `NIAGAHOSTER` section
with the old Express service, a second one with the NestJS rewrite ("This is
the old Deliv Bank service... developed with expressjs" / "new Deliv Bank
service... developed with nestjs"), plus the REDIS section annotated
"still under development". One board documents the migration.

## Block 3 — Supporting lanes

**CI/CD lane:** a horizontal row of stages, each a component with a labeled
connector: `SOURCE (GITHUB)` → `AWS CODEPIPELINE` (Pull Source) → `AWS
CODEBUILD` (Build artifact) → `AWS CODEDEPLOY` (Deploy artifact) → `AWS ECS`
(one per target).

**Flowchart lanes:** one section per scenario (`Not Logged In Flow`, `Normal
Logged Flow`). Notation shared with product flows:

- `ROUNDED_RECTANGLE` = Start / Stop / step.
- `DIAMOND` = decision with **labeled branches** on the connectors:
  `Not Registered` / `Registered`, `Incorrect` / `Correct`, `Retry` /
  `Retry > 3`, `Email exists`, `Phone exists`, `Password not pass regexp`,
  `Redirected`.
- Branches drop to lanes above/below (not just right), and **loop back**
  to a prior node (e.g. `Retry` returns to Login Page, `Not Registered`
  returns to Forget Password Page).
- Where a decision has a side effect worth flagging, attach a sticky note on
  the branch ("Set 1 minutes timeout", "Ngasi token panjang, disimpan sma
  FE").

## Block 4 — Schema + rationale

**Schema:** one `Database Table` widget per real table. Header = table name;
rows = column definition with an optional key marker, name, and type. Types
seen in the reference: `bigint`, `int`, `varchar`, `enum`, `boolean`,
`timestamp`, `longtext`, `serial`; nullable columns get `?` (`int?`,
`varchar?`, `timestamp?`). Flag new columns with a `NEW!!` badge. Link
related tables with a connector (e.g. `transactions → accounts`).

**Rationale stickies:** anchor a sticky near the component/table it explains,
stating the *why*:

- "MongoDB use to store session from our user when they are logging in using
  our mobile application."
- "Redis is used in shared caching and our web sessions."
- "We must specified every endpoint that will be exposed to the public."
- "Better to use docker in our backend app, so we can deploy the image
  instead of cloning from the source code."
- "We need to save banks' account number and name because ... we don't want
  to make expensive call everytime we need the data."
- "To make user not repeatly paying, we should use a custom wallet and user
  should deposit before checkout."

## Verification

- Context: `USER` on the left; `3RD PARTIES` far right when the system
  calls out.
- Every component sits inside exactly one boundary section (AWS /
  NIAGAHOSTER / VPN); logical layers are nested subsections inside it.
- Components are `SQUARE`; data stores/caches/queues are cylindrical
  (`ENG_QUEUE` / `ENG_DATABASE`); annotations are `ELLIPSE`.
- Data flows left→right; every connector is labeled with the interaction or
  data semantics it carries; no crossing connectors.
- Auto-scaled instances fan from the load balancer; read replicas fan from
  the writer with `Read data`.
- CI/CD lane: SOURCE → CODEPIPELINE → CODEBUILD → CODEDEPLOY → ECS, each
  step labeled.
- Flow sections: `ROUNDED_RECTANGLE` steps, `DIAMOND` decisions, every
  branch labeled, loops return to a real node.
- Every real table has a `Database Table` widget with types and `?` on
  nullable columns; new columns are badged `NEW!!`.
- Every non-obvious choice has a rationale sticky anchored to the thing it
  explains.
