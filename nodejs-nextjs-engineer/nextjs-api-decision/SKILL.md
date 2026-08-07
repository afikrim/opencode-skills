---
name: nextjs-api-decision
description: Decide where backend logic belongs in a Next.js project — Route Handlers (app/api), Server Actions, Server Component data fetching, a separate standalone API, or plain React (Vite/SPA). A decision framework with trade-offs and concrete rules: when the app's own UI needs data/mutations, when public third-party endpoints are required, when you need a shared multi-consumer API, and when React alone (no Next.js) is the right call. Use when the user is unsure whether to build a Next.js API route, a separate backend service, or a plain React frontend for a feature. Triggers on "route handler vs server action", "nextjs api vs separate api", "next.js or plain react", "when to use nextjs", "spa vs ssr", "api decision".
---

# Next.js: Where Should the Backend Live?

A decision framework for where logic/API belongs. Four placements, with clear
triggers.

## The Four Options

### A. Server Component data fetching + Server Actions (in-app backend)

Logic runs inside Next.js on the server, no HTTP endpoint exists. This is the
**default** for everything the app's own UI does.

### B. Route Handlers (`app/api/**/route.ts`)

Public HTTP endpoints inside Next.js. Use when something **outside the app's
UI** needs to talk to you over HTTP.

### C. Separate standalone API (own service/deployable)

A backend service outside Next.js (Node/Go/etc., own domain). Use when the API
serves multiple consumers, needs to outlive the frontend, or has requirements
Next.js's server can't meet.

### D. Plain React (Vite/SPA, no Next.js)

A client-only React app with no server. Use when there is no need for a server
at all.

---

## The Decision Tree

```
Does the data/logic serve ONLY your Next.js app's own UI?
├─ YES → Can a Server Component fetch it (no interactive client-only input)?
│        ├─ YES → OPTION A (RSC fetch, direct from source)
│        └─ NO (needs client-side interaction/polling) →
│             Is it a mutation (form, button, POST)?
│             ├─ YES → OPTION A (Server Action)
│             └─ NO  → Client-side fetch of... 
│                      your own data? → fetch from OPTION C if exists, else
│                        evaluate OPTION C or fetch via the data source
│                      external API? → fetch server-side in RSC and proxy
│                        through a Route Handler ONLY if client must call it
└─ NO (external clients need HTTP) →
     Who consumes it?
     ├─ Third parties (webhooks, callbacks, other systems) →
     │     Single consumer, small scope, lives with the app?
     │     ├─ YES → OPTION B (Route Handler)
     │     └─ NO  → OPTION C (separate API)
     ├─ Mobile apps / other frontends / public SDK →
     │     OPTION C (separate API)
     └─ Just the browser but you want to avoid exposing secrets / CORS →
          OPTION B (Route Handler proxy, keeps tokens server-side) or
          OPTION C if more than one client needs it
```

---

## Rules of Thumb

### Use Option A (in-app: RSC + Server Actions) when

- The data/mutation is **only for your app's own pages**.
- You want the least moving parts: no HTTP round-trip, no new deployable.
- You need server-side secrets (DB creds, API tokens) without exposing them.
- Examples: user profile page, dashboard list, signup form, "save" buttons.

### Use Option B (Route Handlers) when

- A **third party must reach you over HTTP**: webhooks (Stripe, GitHub,
  CMS revalidation), OAuth callbacks, `/rss.xml`, `sitemap.xml`, `.well-known`.
- A **client-side component must call your server** and a Server Action can't
  express it (e.g. an external client or a JS client that isn't React).
- You need a thin proxy to hide secrets/CORS when the consumer is the browser
  but the real source is an external API (use a catch-all `[...slug]/route.ts`
  or a specific endpoint).
- It's a genuinely public, cacheable/static endpoint
  (`GET` + `force-static` or `'use cache'`).

### Use Option C (separate API) when

- More than one consumer: **mobile apps, other SPAs, partner integrations,
  public API/SDK** — not just your Next.js UI.
- The API is expected to **outlive / evolve independently** of the frontend,
  or is versioned for external clients.
- Requirements Next.js can't meet: long-running jobs, WebSockets (hosts
  terminate idle connections), background workers, non-HTTP protocols, heavy
  compute, or a different team/ownership boundary.
- You already have a backend; Next.js then only does the frontend + BFF
  orchestration (RSC calls the API directly server-side).

### Use Option D (plain React) when

- There's **no server-side requirement at all**: no SEO for the content,
  no server-only secrets, no SSR benefits.
- Your app is an internal tool / authenticated dashboard that shells out to an
  existing API (a pure client).
- Everything is client-only (auth'd SPA, embedded widgets, admin panels).
- You don't need routes/static optimization Next.js gives you for free.
- Decision shortcut: if there is no use for any of Option A/B/C, then Option D.

---

## When Next.js Does NOT Replace Your Backend (docs caveats)

- Next.js backend capabilities are **not a full backend replacement** — they're
  an API layer: publicly reachable, handles HTTP, returns any content type.
- Route Handlers on serverless hosts **can't share state between requests**,
  can't write to the local filesystem reliably, and **long-running handlers /
  WebSockets get terminated** by timeouts. Long-lived/streaming workloads →
  Option C.
- **Never call your own Route Handlers from Server Components** — extra HTTP
  round-trip at runtime, build-time failure at build. Server Components fetch
  the source directly (Option A), or the external API (Option C).
- Server Actions are queued and **not for data fetching** — don't use them to
  GET data; that's what RSC direct fetching or client-side fetching is for.

## Worked Examples

| Situation | Choice |
|---|---|
| Signup form on your own site | A — Server Action |
| Dashboard page showing DB rows | A — RSC fetch directly |
| Stripe webhook receiving payments | B — Route Handler |
| CMS tells you content changed (revalidate) | B — Route Handler |
| Mobile app + web app share an API | C — separate API |
| Public partner API with versioning | C — separate API |
| Internal admin tool, existing backend | D — plain React (or Next SPA) |
| Content site with no interactivity | D-ish — but Next static still helps SEO |
| Client page that must poll a server every 5s | C (or B proxy) — via swr/react-query |

## Verification

- For the chosen option, the "worked examples" and decision tree agree.
- If Option A: no self-HTTP round-trip; mutation via Server Action; data via
  RSC direct fetch.
- If Option B: endpoint is consumed by a non-UI client or a client-side need
  that can't be a Server Action; secrets stay server-side.
- If Option C: multiple consumers or requirements Next.js can't satisfy;
  Next.js calls it server-side in RSC when possible.
- If Option D: no server-side requirement exists (no SEO/secrets/SSR need).
- Mixed patterns are allowed (A for UI + B for webhooks + C for mobile) — but
  each feature should map to exactly one option.
