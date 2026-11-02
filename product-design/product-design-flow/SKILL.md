---
name: product-design-flow
description: Turn a raw product idea into a complete product design flow board with six blocks — ideation, user research/context, product concept, user flows (flowcharts), data notes, and business rules — following the Duitin (Dong-Feng Hack) standard. Covers the flowchart notation (Start/Stop rounded rects, process squares, decision diamonds, labeled Yes/No connectors), lane layout, sub-flow expansion, and node naming conventions. Use when the user wants to design a product, map user flows, spec an app's screens/behaviors, run ideation-to-rules thinking, or asks to "design the flows", "product flow", "turn this idea into a product", "user flow diagram", "flowchart the app". Triggers on "product design flow", "user flow", "flowchart", "ideation", "design the onboarding flow".
---

# Executable PRD Skill

Create lean PRDs that can be consumed directly by AI coding agents.

## Rules

- Keep the PRD short and dense.
- Organize the PRD around independently understandable features.
- Define product behavior, business rules, acceptance criteria, and material technical constraints.
- Do not include implementation task lists or code-level implementation plans.
- Use normative language: SHALL, MUST, MAY, MUST NOT, SHALL NOT.
- Make every requirement observable and testable.
- Make acceptance criteria binary and independently verifiable.
- Cover happy path, validation, authorization, edge cases, failures, persistence, idempotency, and integrations when relevant.
- Use explicit non-goals to constrain scope.
- Include technical definitions when they remove ambiguity.
- Technical definitions may include architecture, component boundaries, data relationships, flows, sequence diagrams, API contracts, integration contracts, and technical constraints.
- Use Mermaid for diagrams.
- Add diagrams only when they communicate non-trivial behavior or system structure.
- Include API contracts when APIs are part of the feature and the contract affects implementation or integration.
- Define API method, path, auth, request, response, status codes, validation, and important errors when relevant.
- Keep technical definitions at the contract/boundary level; leave implementation choices to the coding agent unless explicitly constrained.
- Include data models only when relationships, invariants, or important fields materially affect implementation.
- Keep Definition of Done short and outcome-oriented.
- Do not duplicate requirements across sections.
- Do not add traditional PRD sections unless they are needed for execution.

## Default Structure

```markdown
# PRD: <Name>

## Context

## Goals

## Non-goals

## Features

### <Feature>
#### Requirement
#### Business Rules
#### Acceptance Criteria
#### Technical Definition
#### API Contract
#### Flow
#### Sequence

## System Architecture

## Data Model

## Technical Constraints

## Definition of Done
```

Omit empty or irrelevant sections.

## Feature Rules

Each feature must define:

- requirement
- acceptance criteria

Add only when applicable:

- business rules
- technical definition
- API contract
- flow
- sequence

A feature should be understandable and testable without requiring unrelated sections.

## Acceptance Criteria Format

Prefer:

```text
AC-001: WHEN <condition>, THEN <observable result>.
```

Use `AND` for additional observable outcomes.

Avoid vague criteria such as:

- user-friendly
- works correctly
- fast
- handles errors properly

Replace them with measurable or observable behavior.

## Technical Definition

Define constraints, interfaces, boundaries, and material system behavior.

Prefer:

```text
PostgreSQL is the source of truth.
ISBN uniqueness SHALL be enforced at the database level.
```

Avoid prescribing internal implementation unless required:

```text
Create BookService.createBook() and BookRepository.findByISBN().
```

## Diagrams

Use Mermaid.

Architecture diagrams show major components, stores, external systems, and communication paths.

Flowcharts show business decisions and state transitions.

Sequence diagrams show ordering, asynchronous processing, retries, external calls, and responsibility boundaries.

## API Contracts

When relevant, define:

- method and path
- authentication/authorization
- request shape
- response shape
- status codes
- validation rules
- important errors

## Agent Behavior

When using the PRD, the coding agent SHALL:

1. Read the complete PRD.
2. Identify target features and dependencies.
3. Inspect the existing repository and conventions.
4. Derive the implementation plan.
5. Implement only defined scope.
6. Add or update relevant tests.
7. Validate acceptance criteria explicitly.
8. Report material ambiguities or contradictions.

When an implementation choice is unspecified, prefer the simplest solution compatible with the existing architecture, conventions, constraints, and acceptance criteria.

Do not invent product behavior to resolve material ambiguity.

## Definition of Done

At minimum:

- all acceptance criteria pass
- relevant tests pass or are added
- defined technical contracts are respected
- no out-of-scope behavior is introduced

## Reference

See [`example.md`](./example.md) for a complete example.
