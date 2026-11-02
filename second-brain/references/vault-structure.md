# Vault structure

Vault root: `~/Documents/volta` (an existing Obsidian vault — `.obsidian/` already lives there, Obsidian is already pointed at it).

## Why 4 segments, not 5

The vault started with Personal/Life/Work/Career/Goals as five peer folders, but Personal and Life had no principled boundary (is "learning Spanish" personal or life?), and Goals duplicated whatever segment the goal was actually about. This is a known failure mode in PKM design, not just bikeshedding:

- **PARA** (Tiago Forte, *Building a Second Brain*) sorts by actionability, not topic, and doesn't have a "Goals" bucket at all — a goal with a deadline is a **Project** (closes when achieved), an ongoing standard to maintain (health, finances, career) is an **Area**.
- **LYT** (Nick Milo) replaces rigid folders with MOCs (Maps of Content) — a hub note that links out to evidence living elsewhere, rather than owning the evidence itself.

So the vault merged Personal+Life into one Area-style segment, and reframed Goals as a thin index (MOC-style) rather than a place facts live in.

## The 4 segments

| Folder | Segment | Holds |
|---|---|---|
| `00-Personal/` | `personal` | Everything outside work, split into topic subfolders (below). |
| `01-Work/` | `work` | Everything job-related — project/topic notes, plus the codebase-wiki. |
| `02-Career/` | `career` | Evidence of professional growth, split by kind (below). This is the segment feeding the senior-promotion push. |
| `03-Goals/` | `goals` | One thin tracker note per active goal (any domain) — target, status, and links out to evidence in the other three segments. **Never the evidence itself** — if you're tempted to write more than target/status/links, that content belongs in Personal/Work/Career instead. |

### Inside `00-Personal/`

Subfolders by topic — this is the established vocabulary, but it's not a hard enum; add a new one if something genuinely doesn't fit:

- `Health/` — fitness, medical, sleep, diet
- `Relationships/` — family, friends, social
- `Home-Finance/` — housing, budgeting, bills, admin logistics
- `Hobbies/` — anything pursued for its own sake (an instrument, a game, a sport)
- `Travel/` — trips, planning, travel-specific facts

### Inside `01-Work/`

Two different organizing schemes live side by side, because the user asked for both:

- `01-Work/<project-or-topic>/` — regular work notes, one subfolder per project or topic (e.g. `01-Work/payments-api/`, `01-Work/hiring-loop/`).
- `01-Work/codebase-wiki/<repo-name>/` — one note per specific problem encountered in that repo (e.g. `01-Work/codebase-wiki/payments-api/docker-healthcheck-timeout.md`). Keep it to concrete problem → cause/fix notes, not general project notes — those go in the project folder instead.

A repo can have both a `01-Work/<repo>/` project folder (roadmap, decisions, meeting notes) and a `01-Work/codebase-wiki/<repo>/` folder (bugs and fixes) — they answer different questions, don't merge them.

### Inside `02-Career/`

Subfolders by kind of evidence:

- `skills/` — a skill exercised or newly picked up
- `feedback/` — feedback received (from anyone — manager, peer, report)
- `learning-log/` — a concept, pattern, or lesson that finally clicked

### Inside `03-Goals/`

Flat, no subfolders — the point is to keep the number of these notes small. Each one ends with a `Related:` line linking to its evidence notes (see querying below), and gets updated in place as status changes rather than spawning new notes per update.

## Note format

Every note (except `03-Goals/` trackers and the handful of index/MOC notes) is **at most 10 lines of body content** and contains **one specific, reusable fact** — not a summary of a conversation, not several facts bundled together. If you catch yourself writing "and also," split it into two notes and link them.

Frontmatter schema:

```yaml
---
id: 202609071423
title: Docker healthcheck timeout on staging
aliases: [Docker healthcheck timeout]   # optional, only if there's a real alternate name
segment: work
project: payments-api                    # work notes with a project (mutually exclusive with repo)
repo: payments-api                       # work notes under codebase-wiki (mutually exclusive with project)
area: Health                             # personal notes only
type: skill                              # career notes only: skill | feedback | learning
supersedes: 202608301090-old-slug        # only if this note revises an earlier one
superseded_by: 202609071500-new-slug     # only present once a LATER note has revised this one
tags: [docker, timeout]
created: 2026-09-07
---
```

Only the fields relevant to the note's segment are present — a personal note has no `project`/`repo`/`type`, etc.

Body: the fact itself, plus optional trailing lines: `Related: [[other-note-id-slug]]` for cross-links, and `Supersedes: [[...]]` / `Reason: ...` when this note revises an earlier one.

## Revision history — never overwrite a fact

A note is a permalinked historical record, so once written, its core fact/decision is never edited in place — see `scripts/new_note.py --supersedes`/`--reason` and the "Revising a decision" section of `SKILL.md` for the full workflow. In short: a correction is a *new* note linked back to the old one, not a rewrite. The vault is also a git repo (`git init` already run), and every `new_note.py` invocation auto-commits, so `git log -p <path>` is a second, independent way to see a note's full history even outside the supersede convention — e.g. if something was ever hand-edited outside the script. `query_vault.py --exclude-superseded` filters stale notes out of normal lookups without deleting anything.

## The permalink scheme

The filename `<id>-<slug>.md` — e.g. `202609071423-docker-healthcheck-timeout.md` — is the permanent link target and **never changes**, even if you later retitle the note. `id` is a minute-resolution timestamp, so it's naturally unique and sortable. Link to notes with a plain Obsidian wikilink using that filename: `[[202609071423-docker-healthcheck-timeout]]`. If the displayed title needs to change later, edit `title:` (and add the old name to `aliases:`) — the filename and every link pointing at it stay valid. Moving a note to a different folder later doesn't break links either, since Obsidian resolves wikilinks by filename across the whole vault.

Always create notes with `scripts/new_note.py` rather than by hand — it computes the id, slugifies the title, resolves the right folder for the segment/area/project/repo/type, writes the frontmatter, and warns if the body is running long. See its `--help` for the full flag list.

## Folder linking — every folder gets a `<folder-name>.md` index

Obsidian wikilinks resolve to files, never to folders — `[[00-Personal]]` is a dead link if there's no `00-Personal.md` anywhere. So every folder in the vault, at every depth, has an index note living inside it named exactly after the folder (e.g. `01-Work/codebase-wiki/payments-api/payments-api.md`), and:

- Every content note ends with a `Parent: [[...]]` line pointing at its containing folder's index.
- Every folder index itself has a `Parent: [[...]]` line pointing at its own parent folder's index — all the way up to `Welcome.md` at the vault root, which is the one folder ("the vault itself") that doesn't need a same-named index since it already has its own home page.

`scripts/new_note.py` creates these automatically and recursively — when you file a note three folders deep, it backfills any missing index note along the entire chain up to the root, not just the immediate folder. You never create or maintain these by hand.

Two folders can legitimately share a name (e.g. a `01-Work/payments-api/` project folder and a `01-Work/codebase-wiki/payments-api/` repo folder both want `payments-api.md`) — this is fine and not a collision, because every `Parent:`/index link the script writes is the full vault-relative path (`[[01-Work/codebase-wiki/payments-api/payments-api|payments-api]]`), never a bare name, so Obsidian never has to guess which one you meant.

An index note's frontmatter has `kind: index` (instead of `segment`/etc.) so `query_vault.py --kind note` can filter navigation notes out of a content search, or `--kind index` to browse just the folder structure. Since an index note's only job is to say "here's your way up," don't add content to it beyond the `Parent:` line — if you want a folder overview page with real content, that's a description worth putting in the individual notes it contains instead, discoverable via the index's backlinks pane (see querying below).

## Querying fast without extra plugins

Two native-Obsidian mechanisms do the "fast query" job the user wants for the career-goal push, with no plugin dependency:

1. **Backlinks as a live dashboard.** Every Career/Work/Personal note that's evidence toward a goal ends its body with `Goal: [[<goal-note-id>]]`. Open the goal note in Obsidian and its backlinks pane shows every linked note — an always-up-to-date dashboard with zero maintenance, and it's exactly what keeps `03-Goals/` thin: the goal note doesn't need to restate the evidence, the backlinks pane already shows it. The same trick is what makes folder indexes work as browsable hubs without manual upkeep: since every child note links `Parent:` up to its folder's index, that index's backlinks pane automatically lists its immediate children — open `payments-api.md` and its backlinks pane is a live table of contents for that repo's codebase-wiki entries.
2. **Tags as a filter axis.** Use consistent tags — `career/skill`, `career/feedback`, `career/learning` for Career notes; project or repo name as a tag for Work notes — and use Obsidian's tag pane or `search tag:#career/skill` to slice the vault instantly.

If the user later installs the Dataview plugin, these same conventions (frontmatter fields, tags, `Goal:` links) are already Dataview-queryable — nothing here needs to change to take advantage of it.

## Optional: the `obsidian-cli` skill

A separate skill (`obsidian-cli`) is already installed and can drive a *running* Obsidian instance (search, create, backlinks, tasks, etc.) via the `obsidian` CLI. It's a fine convenience when Obsidian happens to be open, but don't depend on it for the automatic recap behavior — that has to work whether or not the app is open, so it always goes through `new_note.py` / direct file writes instead.
