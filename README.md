# opencode-skills

Personal collection of [opencode](https://opencode.ai) skills.

## Installation

Clone this repo and register it via `skills.paths`:

```sh
git clone git@github.com:afikrim/opencode-skills.git ~/.config/opencode/opencode-skills
```

Then add to `opencode.json`:

```json
{
  "skills": {
    "paths": ["opencode-skills"]
  }
}
```

Restart opencode.

## Skills

- **hexagonal-architecture** — Go hexagonal (ports & adapters) layout with thin
  handlers/adapters (no tests needed) and dto+mapper patterns.
- **unit-test** — unit tests scoped to pure functions only: mappers,
  transformers, helpers.
- **functional-test** — functional tests for the business logic implementation
  (service layer), with ports mocked.
- **integration-test** — full-stack wiring tests with go-sqlmock (mock DB) and
  WireMock (mock external APIs), compared against golden files/fixtures.

## License

MIT
