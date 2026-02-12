# AGENTS.md — PySequence

## Quick Reference

```bash
just install          # Install dependencies (for IDE support)
just fmt              # Format code with Black
just lint             # Check formatting (no changes)
just test-unit        # Run unit tests in Docker
just check            # Run lint + unit tests (full local CI)
just build            # Build all Docker images
just api-up           # Start the API server
just bot-up           # Start the Telegram bot
```

Add `--op` to inject secrets via 1Password: `just test-unit --op`

## Architecture Overview

**Monorepo — 4 packages, each independently deployable:**

```
packages/
  pysequence-sdk/        # GraphQL SDK (curl_cffi + Playwright)
  pysequence-api/        # FastAPI REST server (depends on SDK)
  pysequence-client/     # HTTP client for the REST server (standalone)
  pysequence-bot/        # Optional Telegram bot (depends on SDK)
```

**Dependency graph:**
```
pysequence-client → (HTTP) → pysequence-api → pysequence-sdk → (GraphQL) → Sequence.io
                                                    ↑
                              pysequence-bot ────────┘
```

- **SDK** — Core. Auth0 tokens, GraphQL client, Pydantic models, shared safeguards.
- **API** — REST trust boundary for external services. API-key auth, transfer limits, audit trail.
- **Client** — Standalone HTTP client for consuming the REST API. No SDK dependency.
- **Bot** — Telegram bot with Claude AI agent. Uses SDK directly (not the API).

## Code Conventions

### Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>
```

Types: `feat`, `fix`, `chore`, `docs`, `ci`, `test`, `refactor`

Examples:
- `feat: add pod transfer history endpoint`
- `fix: handle empty agent response in Telegram bot`
- `chore: bump version to 0.3.1`

### Formatting

- **Black** — all Python code, enforced in CI
- Run `just fmt` to format, `just lint` to check

### Testing

- **pytest** in Docker via `just test-unit`
- Unit tests: no external dependencies, mock the SDK
- Integration tests: `just test-integration --op` (requires 1Password secrets)

### Branch Naming

```
feature/<kebab-case-description>
fix/<kebab-case-description>
chore/<kebab-case-description>
docs/<kebab-case-description>
```

## Contribution Rules

- **One logical change per PR** — don't mix unrelated changes
- **Squash merge** — PR title becomes the commit message on `main`
- **CI must pass** — `just lint` + `just test-unit` + PR title check
- **PR title = Conventional Commits format** — enforced by CI

## Common Patterns

### Browser-Compatible HTTP

The SDK uses `curl_cffi` with Chrome TLS fingerprinting. All HTTP requests must include browser-matching headers (`origin`, `referer`, `sec-fetch-*`, `x-request-id: webapp-<uuid>`).

### GraphQL Must Match the Webapp

Query strings, fragment names, field selections, and `__typename` inclusions must exactly match what the Sequence webapp sends. Do not invent new queries.

### Shared Safeguards

`AuditLog` and `DailyLimitTracker` live in `pysequence_sdk.safeguards` and are shared by both the API server and the bot. Do not duplicate safeguard logic.

### Single SequenceClient Per Server

All requests share one `SequenceClient` instance so rate limiting works correctly. Do not create multiple instances.

### Secrets vs Config

- **Secrets** (`SEQUENCE_*`, `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`) — always environment variables
- **Non-secret config** (model, limits, system prompt) — `bot-config.yaml`, mounted into Docker

### Token Management

Fully automated via `get_access_token()`. Tokens cached in `.tokens.json`. Consumers never manage tokens directly.

## Do Not

- Add Node.js dependencies to this project
- Use raw `poetry run` when a `just` recipe exists
- Modify GraphQL queries without matching the webapp
- Commit `.tokens.json`, `.env`, or any secrets
- Create multiple `SequenceClient` instances in a single server
- Over-engineer — only build what's needed

## Skills

Agent skills are defined in `.agents/skills/`. Each skill has a `SKILL.md` with instructions:

- **validate** — Run lint + unit tests, auto-fix formatting issues
- **commit** — Stage changes and create a Conventional Commits message
- **pr** — Create a branch, push, and open a PR with proper formatting
