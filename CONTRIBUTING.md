# Contributing to PySequence

## Prerequisites

- Python 3.11+
- [Poetry 2.x](https://python-poetry.org/)
- [Docker](https://www.docker.com/) (tests run in containers)
- [just](https://github.com/casey/just) (task runner)

## Development Setup

```bash
# Install dependencies locally (for IDE support)
just install

# Run unit tests
just test-unit

# Format code
just fmt

# Check formatting without changes
just lint

# Full local CI check (lint + tests)
just check
```

Add `--op` to any recipe to inject secrets via 1Password:

```bash
just test-unit --op
```

## Commit Conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/). Every commit message (and PR title) must follow:

```
<type>: <description>
```

### Types

| Type | When to use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `chore` | Maintenance (deps, version bumps, config) |
| `docs` | Documentation changes |
| `ci` | CI/CD workflow changes |
| `test` | Adding or updating tests |
| `refactor` | Code restructuring without behavior change |

### Examples

```
feat: add pod transfer history endpoint
fix: handle empty agent response in Telegram bot
chore: bump version to 0.3.1
docs: update SDK usage examples
ci: add format check to PR workflow
test: add unit tests for daily limit tracker
refactor: extract GraphQL query builder
```

## Branch Naming

Create branches with a type prefix and kebab-case description:

```
feature/add-transfer-history
fix/empty-response-handling
chore/bump-dependencies
docs/update-api-examples
```

## Pull Request Process

1. **One logical change per PR** — don't mix unrelated changes
2. **Branch from `main`** — keep your branch up to date
3. **PR title = Conventional Commits format** — this becomes the squash commit message
4. **CI must pass** — format check, unit tests, and PR title validation
5. **Squash merge** — all PRs are squash merged into `main`

### Before Submitting

```bash
# Run the full local CI check
just check
```

This runs `just lint` (format check) and `just test-unit` (unit tests in Docker).

## Testing

- **Unit tests**: `just test-unit` — run in Docker, no external dependencies
- **Integration tests**: `just test-integration --op` — require 1Password secrets
- **All tests**: `just test-all --op` — unit + integration

Write tests for new functionality. Unit tests should mock external dependencies (SDK client, API calls).

## Code Style

- **Formatter**: [Black](https://black.readthedocs.io/) — enforced in CI
- Run `just fmt` before committing to auto-format
- Run `just lint` to check without making changes
