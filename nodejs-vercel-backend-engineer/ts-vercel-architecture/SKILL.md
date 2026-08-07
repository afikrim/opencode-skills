---
name: ts-vercel-architecture
description: Deploy a TypeScript hexagonal architecture app to Vercel as serverless Functions. Builds on the generic ts-hexagonal-architecture layout (Hono + Drizzle + core/ports/service/adapters/handlers), adding the Vercel-specific entrypoint: a single api/[[route]].ts catch-all Function that mounts the Hono app via the hono/vercel handle() adapter, runtime selection (edge vs nodejs), and vercel dev/deploy workflow. Use when the user asks to deploy a Hono TypeScript app to Vercel, create api/[[route]].ts, use hono/vercel handle, choose edge or nodejs runtime, or run the app with vercel dev. Triggers on "vercel", "hono/vercel", "handle", "api/[[route]].ts", "deploy to vercel", "edge runtime", "vercel functions".
---

# Hexagonal Architecture on Vercel (TypeScript)

This skill is the **Vercel layer** on top of the generic
`ts-hexagonal-architecture` skill. Apply that skill for the full layout
(`src/core`, `src/ports`, `src/service`, `src/adapters`, `src/handlers`,
Drizzle, dto/mapper patterns, zod config). This skill only changes the
**entrypoint and deployment story**.

Everything below is identical to the generic skill; the only Vercel-specific
difference is **how the Hono app is exposed** — a single catch-all Function in
`api/[[route]].ts`.

## Why one catch-all file

Vercel treats every file under `api/` as a separate Function (and you pay
cold-start/allocated-compute per function). A **catch-all** `[[route]]` file
captures every path under `/api` into a single Function, so the entire Hono
app (all routes) is one deployable unit with one cold start. That matches how
hexagonal apps already funnel everything through one Hono router.

## The Vercel Adapter: `hono/vercel`

Hono ships an official Vercel adapter. Import `handle` from `hono/vercel`
(not `hono/node-server` — that one starts its own HTTP server and is for
self-hosted Node):

```ts
// api/[[route]].ts
import { handle } from 'hono/vercel'
import { createApp } from '../src/app'

export const config = {
  runtime: 'edge', // or 'nodejs' — see Runtime Notes
}

export default handle(createApp())
```

- `handle(app)` wraps the Hono app into a Vercel-compatible handler
  (`(req: Request) => Response`). Vercel calls the default export for every
  matched request.
- The default export is the only thing Vercel invokes. No HTTP server is ever
  started — Vercel manages invocation, scaling, and lifecycle.
- Keep this file **empty of logic**: it imports a pre-wired `createApp()` and
  exports the handler. All route wiring lives in `src/handlers/routes.ts`
  exactly as the generic skill describes.

## Runtime Notes

- `runtime: 'edge'` runs on the Vercel Edge Runtime: fast cold starts, no
  Node.js APIs, Web-standard runtime. Works if your adapters use only
  Web-standard APIs (`fetch`, HTTP drivers). Drizzle's `neon-http`,
  `drizzle-orm/http-proxy` / edge-compatible drivers work here.
- `runtime: 'nodejs'` runs on the Node.js runtime and supports full Node APIs
  (`node-postgres` TCP pools, `fs`, `crypto`, etc.). Choose nodejs when an
  adapter needs a TCP connection, native module, or a Node-only library.
- Pick per Function. If one route needs Node-only features, you can split it
  into its own file under `api/` with `runtime: 'nodejs'` while the rest stays
  edge — but prefer the single catch-all unless you have a real reason.
- Whatever you pick, run locally with `vercel dev` (not `tsx src/index.ts`) so
  routing/runtime matches production.

## Local Development

```sh
npx vercel dev
```

- Serves the app at `http://localhost:3000`, applying the same `api/`
  catch-all routing as production.
- Loads env vars from `.env` / `.env.local` / Vercel project settings. No
  `dotenv` call needed in the function.

## Environment Variables

Vercel injects env vars at deploy time from project settings (or `vercel env
add`). Still validate with the zod config from the generic skill — fail fast at
import time if a required var is missing:

```ts
// src/config/config.ts
const envSchema = z.object({
  DATABASE_URL: z.string().url(),
  // ...
})
```

- Use the same `src/config/config.ts` as the generic skill; Vercel env just
  fills `process.env` the same way a `.env` file would.
- Sensitive values are managed in the Vercel dashboard / CLI, never committed.
  `.env.local` is git-ignored.

## Deployment

```sh
npx vercel dev       # local
npx vercel           # preview deployment
npx vercel --prod    # production
```

- Vercel auto-detects the `api/` Functions convention; no `vercel.json`
  routing needed for the catch-all.
- On deploy, `api/[[route]].ts` becomes the `/api/*` Function and everything
  the app exposes through Hono is reachable under that prefix.

## Composition Root

Exactly like the generic skill — `createApp()` in `src/app.ts` builds
adapters → services → handlers → Hono routes. The catch-all only mounts it:

```ts
// src/app.ts
export function createApp(overrides?: { db?: DB }): App {
  const db = overrides?.db ?? defaultDb
  const userRepo = new PostgresUserRepository(db)
  const userService = new UserService(userRepo)
  return new Hono().basePath('/api').route('/users', createUserRoutes(userService))
}

// api/[[route]].ts
export default handle(createApp())
```

## Verification

- `npx vercel dev` serves the app locally and routes match production.
- `npm run build` (tsc) passes.
- `api/[[route]].ts` contains no logic — only `import { handle } from 'hono/vercel'`,
  `export const config`, and `export default handle(createApp())`.
- Confirm `hono/vercel` is the adapter used, not `hono/node-server`.
- `npx vercel --prod` deploys; hit `/api/...` to confirm the catch-all routes.
- Confirm no Drizzle/Hono types leak into `core/` (see generic skill checks).
