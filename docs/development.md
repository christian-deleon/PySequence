# Development

## Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/) 2.x
- Docker & Docker Compose
- [just](https://github.com/casey/just) (command runner)

## Repository Structure

```
PySequence/
├── packages/
│   ├── pysequence-sdk/        # Core GraphQL SDK
│   ├── pysequence-api/        # FastAPI REST server
│   ├── pysequence-client/     # HTTP client for REST API
│   └── pysequence-bot/        # Telegram bot
├── docs/                      # Documentation
├── Dockerfile                 # Multi-stage (prod, bot, dev)
├── compose.api.yaml           # API server deployment
├── compose.bot.yaml           # Bot deployment
├── compose.dev.yaml           # Dev/test environment
├── bot-config.yaml            # Bot configuration template
├── justfile                   # Task runner recipes
├── pyproject.toml             # Root project config
└── poetry.lock
```

Dependency graph:

```
pysequence-client -> (HTTP) -> pysequence-api -> pysequence-sdk -> (GraphQL) -> Sequence.io
                                                      ^
                                pysequence-bot -------/
```

## Local Setup

```bash
# Install all dependencies (including dev)
just install

# Or manually:
poetry install
```

This installs all four packages in development mode for IDE support.

## Testing

All tests run in Docker:

```bash
just test-unit              # Unit tests
just test-integration       # Integration tests (hit real API)
just test-all               # All tests
```

Test configuration:

- Tests are in `packages/*/tests/`
- Integration tests are marked with `@pytest.mark.integration`
- Integration tests are excluded by default (need real credentials via environment variables)
- Integration tests run with `-x` (stop on first failure) and 120s timeout

## Code Style

```bash
just fmt    # Format with Black
```

## Release Process

```bash
just release 0.3.0
```

This recipe:

1. Verifies clean working tree
2. Verifies on `main` branch
3. Verifies local main is up-to-date with origin
4. Bumps version in all 5 `pyproject.toml` files
5. Commits the version bump
6. Creates a git tag `v0.3.0`
7. Pushes to origin (main + tag)
8. CI publishes packages and Docker images

## Key Architecture Decisions

- **Single SequenceClient per server** -- All requests share one instance so rate limiting works correctly.
- **Browser-compatible requests** -- HTTP requests use curl_cffi with Chrome TLS fingerprinting.
- **GraphQL queries match the webapp exactly** -- Query strings, fragment names, field selections, and `__typename` inclusions must match.
- **Shared safeguards** -- `AuditLog` and `DailyLimitTracker` live in `pysequence_sdk.safeguards` and are used by both the API and bot.
- **Secrets vs config separation** -- Secrets always come from env vars; non-secret bot config lives in `bot-config.yaml`.

## Useful Commands

```bash
just                 # List all available recipes
just install         # Install dependencies
just fmt             # Format code with Black
just reauth          # Delete cached tokens to force re-authentication
just build           # Build all Docker images
just loc             # Code statistics with cloc
```
