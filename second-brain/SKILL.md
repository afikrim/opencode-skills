---
name: second-brain
description: Query and automatically file durable facts into your shared server second brain through its Tailscale MCP server. Markdown is authoritative; MongoDB provides semantic retrieval and Neo4j provides graph links.
---

# Shared Second Brain

The configured server owns the authoritative Markdown vault. MCP endpoint: http://100.70.58.73:8001/mcp over Tailscale. Call its `skill` tool for conventions. Only the configured MCP is authoritative; never use a separate local vault.

For context-dependent questions (main thread only), call MCP `skill`, then `recall` with the user’s question. Use `search_notes` for discovery, `lookup_notes` for exact duplicate checks, and `get_note` for supporting notes. Use MCP tools directly rather than `query_vault.py` for conversational recall. Read only relevant matches; no matches is normal. No broad vault scans.

## Querying

`search_notes` finds semantic matches in MongoDB. `lookup_notes` performs exact substring/metadata matching against authoritative Markdown, including notes awaiting indexing; use it for duplicate checks. `get_note` reads full notes. `related_notes` uses Neo4j links/backlinks.

The compatibility CLI `scripts/query_vault.py` supports --text, --segment, --tag, --project, --repo, --area, --type, --kind, --exclude-superseded, --backlinks-to and --read <vault-relative-path>. It calls the shared MCP and prints relevant remote note bodies. Never open returned paths under another local vault.

## Automatic filing

A detached stop filer evaluates the last exchange after each reply. Codex and Claude use ~/.codex/hooks/second_brain_stop.py; OpenCode uses its second-brain plugin and scripts/stop_filer_opencode.py. SECOND_BRAIN_STOP_FILER_ACTIVE=1 prevents recursive filing.

Only file durable facts, decisions, bug fixes, project status, user preferences or concrete career evidence. Skip small talk, generic knowledge, routine narration and uncertain guesses. Query first, one reusable fact per note, at most ten body lines. Use `create_note` or `scripts/new_note.py`, which now forwards to the shared MCP. Never write Markdown locally or directly mutate Neo4j: the API writes Markdown and the indexer projects it into both databases every sixty seconds. If Tailscale/server is unavailable, report/log the failure; never silently fall back to a separate local vault.

Four segments: personal (area), work (project or repo, mutually exclusive), career (type: skill/feedback/learning), goals (thin trackers linking to evidence). The original API writer creates permanent filenames, metadata, parent indexes and Git history. Link related notes with `links`/`--links`. To revise a historical claim, create a new note with `supersedes` and `reason`; preserve the original fact. Goal trackers are current state and may be updated through a separately authorized workflow.

For explicit remember requests, query then create immediately using MCP or the compatibility CLI. Passive filing is handled by the stop hooks; do not launch an extra filer from the main thread.

## Meaningful knowledge graph

Use `explore_graph(query="Neo4j")` to find named entities, memories, typed connections, and supporting note paths. Follow an exact `node_id` from a result for a focused neighborhood. `related_notes` returns typed note links. Entity identity is scoped by type and normalized name; reuse the same name for the same entity and disambiguate different people or projects.

When creating a durable note, set `memory_type` to fact, decision, learning, preference, goal, skill, feedback, procedure, or observation when supported; otherwise leave memory. Add `entities` for important named subjects and `relations` for explicit claims in the body. Example:

```json
{"memory_type":"fact","entities":[{"name":"Second Brain","type":"System"},{"name":"Neo4j","type":"Technology"}],"relations":[{"source":"Second Brain","type":"USES","target":"Neo4j"}]}
```

Entity types: Project, Repository, Area, Topic, Person, Organization, Technology, Skill, System, Place. Relation types: USES, DEPENDS_ON, BUILT_WITH, RUNS_ON, STORES, INTEGRATES_WITH, OWNED_BY, WORKS_ON, MEMBER_OF, SUPPORTS, CONTRADICTS, ENABLES, BLOCKS, RELATED_TO, INCLUDES, EXCLUDES, REQUIRES, PROVIDES, WRITES_TO, READS_FROM, MIGRATED_TO, MIGRATED_FROM, REPLACES, VERIFIES. Relation endpoints must name entities declared in that note. The CLI accepts `--memory-type`, `--entities '<JSON array>'`, and `--relations '<JSON array>'` and forwards them through MCP.

Record only relationships directly supported by the note body and conversation evidence. Do not turn tag co-occurrence, similarity, or an ambiguous mention into a factual claim. Each graph relationship preserves its supporting note paths and current versus superseded evidence. Revising a claim still uses `supersedes`; historical evidence remains visible. Existing tags and folder metadata project into Topic/Project/Area nodes; Parent links become PART_OF and unclassified wikilinks remain REFERENCES.

Existing evidence can be annotated with `enrich_note(path, expected_digest, memory_type, entities, relations)`. First call `get_note` and use its `content_digest`; the server rejects stale reads. Enrichment replaces graph annotation fields only and preserves the body and other frontmatter. Preserve existing supported annotations when extending them. Use enrichment for extracting what the note already says; changed facts require a superseding note. The CLI equivalent is `remote_brain.py enrich --path <path> --expected-digest <digest> --memory-type <type> --entities '<JSON>' --relations '<JSON>'`.

## LLM graph generation and recall

The configured model performs schema-constrained extraction and intent-aware retrieval. Nomic still supplies MongoDB embeddings. `recall(query)` interprets the user's intention, selects semantic/exact/graph lookups and filters, ranks evidence for actual relevance, and returns a grounded answer, citations, the plan, and uncertainty. `search_notes(query)` uses the same planner but returns notes. Explicit caller filters remain authoritative. `lookup_notes` stays exact and is the inexpensive duplicate-check tool. If no LLM key is configured, search remains vector-only; recall and generation require configuration.

For historical questions the planner can include superseded notes; present-tense answers prefer current evidence. Treat retrieved notes and their citations as evidence, and do not replace missing recorded reasons with general knowledge. Extracted edges are marked `origin: llm` and `assertion_status: extracted`; supporting quotes establish provenance, not guaranteed correctness. A second LLM pass rejects relationships that are not entailed by the source body; entity type/name conflicts with curated annotations are rejected when applying.

`generate_graph(filters={"project":"second-brain"}, limit=10)` queues proposals. Poll `graph_job_status(job_id)` for processed/total, failures, and token usage. Use `include_candidates=true` to inspect bounded proposals. `apply_graph_job(job_id)` applies a completed job through MCP enrichment; stale notes and identity conflicts are rejected. `cancel_graph_job(job_id)` cancels after the active request. `auto_apply=true` is available when automatic extraction is wanted. Jobs resume after service restarts and cached source/model/prompt digests avoid repeat extraction.

When `GRAPH_AUTO_GENERATE=true`, a new MCP note without explicit relations queues extraction automatically. Existing curated relations are preserved. Model credentials belong only in the server's ignored `.env`, never notes, prompts, client templates, or Git.
