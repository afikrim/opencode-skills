---
name: ts-vercel-architecture
description: Deploy a TypeScript hexagonal architecture app to Vercel with Hono. Builds on the generic ts-hexagonal-architecture layout (Hono + Drizzle + core/ports/service/adapters/handlers), adding the Vercel-specific entrypoint: src/index.ts default-exports the Hono app (official vercel/examples hono boilerplate, no api/ directory, no adapter), plus vercel dev/deploy workflow. Use when the user asks to deploy a Hono TypeScript app to Vercel, wire src/index.ts for Vercel, or run the app with vercel dev / vc dev. Triggers on "vercel", "deploy to vercel", "hono on vercel", "src/index.ts", "vercel dev", "vc dev".
---

# Hexagonal Architecture on Vercel (TypeScript)

This skill is the **Vercel layer** on top of the generic
`ts-hexagonal-architecture` skill. Apply that skill for the full layout
(`src/core`, `src/ports`, `src/service`, `src/adapters`, `src/handlers`,
Drizzle, dto/mapper patterns, zod config). This skill only changes the
**entrypoint and deployment story**.

Everything below is identical to the generic skill; the only Vercel-specific
difference is **how the Hono app is exposed** — via `src/index.ts`.

## Entrypoint: `src/index.ts` (official boilerplate)

Follow the official Vercel Hono boilerplate
(`https://github.com/vercel/examples/tree/main/framework-boilerplates/hono`):
Vercel detects the Hono framework preset and serves the app default-exported
from `src/index.ts`. There is **no `api/` directory, no adapter import, and
no `vercel.json` routing** involved.

```ts
// src/index.ts
import { Hono } from 'hono'
import { createApp } from './create-app'

const app: Hono = createApp()

export default app
```

(The boilerplate builds `new Hono()` inline; the hexagonal version imports the
pre-wired `createApp()` instead. Same shape: build the app, default-export
it.)

## Entrypoint selection — read this before naming files

The `@vercel/hono` builder does **not** always pick `src/index.ts`. It scans
candidate filenames in fixed order — `app`, `index`, `server`, `src/app`,
`src/index`, `src/server` (each with js/cjs/mjs/ts/cts/mts extensions) — and
selects the **first** file whose content imports `'hono'`. In particular
`src/app.ts` wins over `src/index.ts`.

Consequences (violating any of these breaks deploys with
`Error: Can't detect way to handle request` / `FUNCTION_INVOCATION_FAILED`):

- The composition-root factory MUST live in a filename the builder never
  scans — e.g. `src/create-app.ts` (`createApp()`), never `src/app.ts`.
- `src/index.ts` MUST itself contain a `hono` import (e.g.
  `import { Hono } from 'hono'`) and MUST default-export the built app
  instance (an object with `.fetch`), never the factory.
- Never give any other scanned filename (`app.*`, `server.*`, `src/server.*`)
  a hono import unless that file default-exports the app instance.

- The default export is the only thing Vercel invokes. No HTTP server is ever
  started — Vercel manages invocation, scaling, and lifecycle.
- Keep this file **empty of logic**: it imports a pre-wired `createApp()` and
  default-exports the app. All route wiring lives in `src/handlers/routes.ts`
  exactly as the generic skill describes.
- The generic skill's `@hono/node-server` `serve()` entrypoint is for
  self-hosted Node only. On Vercel, `src/index.ts` replaces it — do not call
  `serve()` here.

## Do NOT use the `api/` catch-all path

Do **not** create any of the following:

- `api/[[route]].ts` or `api/index.ts` catch-all Functions;
- `import { handle } from 'hono/vercel'` (no adapter is needed — the framework
  preset serves the default export directly);
- `vercel.json` rewrites for API routing;
- esbuild prebuild bundles (`build.mjs`, `api/index.js`,
  `api/package.json` overrides) — these were workarounds for the `api/`
  Functions transpile model and do not apply to the `src/index.ts` preset.

If you see any of these in a repo using this skill, remove them as part of
your change — they conflict with the preset (duplicate route mapping,
ESM/CJS interop failures) and will mislead future work.

## Runtime Notes

- The Hono preset runs on the Node.js runtime by default, so adapters may use
  full Node APIs (`node-postgres` TCP pools, `fs`, `crypto`, Node-only SDKs).
- If you need anything other than the default runtime, consult the current
  Vercel docs rather than guessing at config shapes — do not invent
  `export const config` blocks.
- Whatever the setup, run locally with `vc dev` / `vercel dev` (not
  `tsx src/index.ts`) so routing/runtime matches production.

## Local Development

```sh
npm install
vc dev        # or: npx vercel dev
# open http://localhost:3000
```

```sh
vc build      # build locally, same as production
```

- Serves the app at `http://localhost:3000` with production routing.
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
- The env file for `vercel dev` is written to `.env.local` / `.vercel/.env` by
  `vercel link` / `vercel env pull`; do not commit it.

## Deployment

```sh
# one-time: create + link
vercel link --yes

# push env
vercel env add NAME production
vercel env add NAME preview
vercel env add NAME development

# deploy
vercel --prod --yes   # production
vercel                # preview
```

- `vc deploy` from the boilerplate README maps to the same flow.
- No `api/` Functions convention is involved — the single default export in
  `src/index.ts` is the whole app, so there is one deployable unit and one
  cold start by construction.

## Composition Root

Exactly like the generic skill — `createApp()` in `src/create-app.ts` builds
adapters → services → handlers → Hono routes (the filename matters: see
Entrypoint selection — never `src/app.ts`). `src/index.ts` only instantiates
and default-exports it:

```ts
// src/create-app.ts
export function createApp(overrides?: { db?: DB }): App {
  const db = overrides?.db ?? defaultDb
  const userRepo = new PostgresUserRepository(db)
  const userService = new UserService(userRepo)
  return new Hono().basePath('/api').route('/users', createUserRoutes(userService))
}

// src/index.ts
import { Hono } from 'hono'
import { createApp } from './create-app'

const app: Hono = createApp()

export default app
```

## Verification

- `vc dev` / `npx vercel dev` serves the app locally and routes match production.
- `npm run build` (tsc) passes.
- `src/index.ts` contains no logic — only the `hono` import, `createApp()`
  import, and `export default app`.
- Confirm the factory lives in a builder-invisible filename (`src/create-app.ts`,
  not `src/app.ts`) and no other scanned entrypoint filename imports `hono`.
- Confirm there is no `api/` directory, no `hono/vercel` import, and no
  `vercel.json` routing rewrites for the API.
- `npx vercel --prod` deploys; hit `/api/...` to confirm the routes.
- Confirm no Drizzle/Hono types leak into `core/` (see generic skill checks).
