# Docker

## Overview

All Docker files live at the project root. The `Dockerfile` uses multi-stage builds with three targets: `prod` (API server), `bot` (Telegram bot), and `dev` (testing). The API and bot have separate Compose files so each can be deployed independently.

## Dockerfile

The Dockerfile uses a multi-stage build pipeline:

```
base -> deps -> prod (API server, port 8720)
             -> bot  (Telegram bot)
             -> dev  (all packages + dev dependencies)
```

### Stages

- **`base`** -- Python 3.11-slim with Poetry 2.3.2 installed and configured for in-project virtual environments.
- **`deps`** -- Copies all `pyproject.toml` files from each package so dependency resolution can be cached independently of source code changes.
- **`prod`** -- Installs production dependencies, Playwright with Chromium, and copies source code. Entry point: `python -m pysequence_api`. Exposes port 8720.
- **`bot`** -- Same dependency base as `prod` but with a different entry point: `python -m pysequence_bot.telegram`.
- **`dev`** -- Installs everything including dev dependencies and copies all source code. Used for running tests.

## Compose Files

### API Server (`compose.api.yaml`)

```yaml
name: pysequence-api
services:
  api:
    build:
      target: prod
    restart: unless-stopped
    ports:
      - "8720:8720"
    environment:
      - SEQUENCE_EMAIL
      - SEQUENCE_PASSWORD
      - SEQUENCE_TOTP
      - SEQUENCE_ORG_ID
      - SEQUENCE_KYC_ID
      - SEQUENCE_AUTH0_CLIENT_ID
      - SEQUENCE_API_KEY
      - SEQUENCE_DATA_DIR=/app/data
    volumes:
      - data:/app/data
volumes:
  data:
```

Usage:

```bash
just api-up           # Start the API server
just api-down         # Stop
just api-logs         # Follow logs
```

### Telegram Bot (`compose.bot.yaml`)

```yaml
name: pysequence-bot
services:
  telegram-bot:
    build:
      target: bot
    restart: unless-stopped
    environment:
      - SEQUENCE_EMAIL
      - SEQUENCE_PASSWORD
      - SEQUENCE_TOTP
      - SEQUENCE_ORG_ID
      - SEQUENCE_KYC_ID
      - SEQUENCE_AUTH0_CLIENT_ID
      - TELEGRAM_BOT_TOKEN
      - ANTHROPIC_API_KEY
      - BOT_DATA_DIR=/app/data
      - SEQUENCE_DATA_DIR=/app/data
    volumes:
      - bot-data:/app/data
      - ./bot-config.yaml:/app/data/bot-config.yaml:ro
volumes:
  bot-data:
```

Note the bind mount for `bot-config.yaml` (read-only). Users copy the template, edit it, and mount it into the container -- no code changes needed.

Usage:

```bash
just bot-up           # Start the bot
just bot-down         # Stop
just bot-logs         # Follow logs
```

### Dev/Test (`compose.dev.yaml`)

```yaml
name: pysequence-dev
services:
  dev:
    build:
      target: dev
    environment:
      - SEQUENCE_EMAIL
      - SEQUENCE_PASSWORD
      - SEQUENCE_TOTP
      - SEQUENCE_ORG_ID
      - SEQUENCE_KYC_ID
      - SEQUENCE_AUTH0_CLIENT_ID
      - SEQUENCE_API_KEY
      - SEQUENCE_DATA_DIR=/app/data
      - TELEGRAM_BOT_TOKEN
      - TELEGRAM_USER_NAMES
      - TELEGRAM_GROUP_ID
      - ANTHROPIC_API_KEY
      - BOT_DATA_DIR=/app/data
    volumes:
      - data:/app/data
volumes:
  data:
```

Usage:

```bash
just test-unit           # Run unit tests
just test-integration    # Integration tests
just test-all            # All tests
```

## Building Images

```bash
just build        # Build all images (api, bot, dev)
just api-build    # API server image only
just bot-build    # Bot image only
just dev-build    # Dev image only
```

## Data Persistence

Both API and bot use Docker named volumes (`data:` and `bot-data:`) mounted at `/app/data`. This persists:

- `.tokens.json` -- Auth token cache
- `.audit.jsonl` -- Audit trail of all transfer attempts
- `.daily_limits.json` -- Daily transfer tracking
- `.memories.json` -- Bot memory (bot only)
