# Configuration Reference

All configuration for [PySequence](https://github.com/christian-deleon/PySequence) components. Secrets are always set as environment variables.

## SDK Configuration

These environment variables are required by any component that uses the SDK (API server, Telegram bot, or standalone scripts).

| Env Var | Required | Default | Description |
|---------|----------|---------|-------------|
| `SEQUENCE_EMAIL` | Yes | -- | Login email for GetSequence |
| `SEQUENCE_PASSWORD` | Yes | -- | Login password |
| `SEQUENCE_TOTP` | Yes | -- | TOTP secret for MFA |
| `SEQUENCE_ORG_ID` | Yes | -- | Organization ID |
| `SEQUENCE_KYC_ID` | Yes | -- | KYC application ID |
| `SEQUENCE_AUTH0_CLIENT_ID` | Yes | -- | Auth0 client ID |
| `SEQUENCE_DATA_DIR` | No | `.` | Directory for `.tokens.json`, `.audit.jsonl`, `.daily_limits.json` |

### Notes

- `SEQUENCE_TOTP` is the TOTP secret (not a one-time code). The SDK uses it to generate codes automatically.
- `SEQUENCE_DATA_DIR` controls where the SDK writes its data files. In Docker, this is typically set to `/app/data` backed by a named volume.

## API Server Configuration

In addition to all SDK environment variables above, the API server uses:

| Env Var | Required | Default | Description |
|---------|----------|---------|-------------|
| `SEQUENCE_API_KEY` | Yes | -- | API key for `X-API-Key` header authentication |
| `SEQUENCE_SERVER_HOST` | No | `0.0.0.0` | Server bind host |
| `SEQUENCE_SERVER_PORT` | No | `8720` | Server bind port |
| `SEQUENCE_MAX_TRANSFER_CENTS` | No | `1000000` | Per-transfer limit in cents ($10,000) |
| `SEQUENCE_MAX_DAILY_TRANSFER_CENTS` | No | `2500000` | Daily cumulative transfer limit in cents ($25,000) |

### Notes

- The API server uses a single shared `SequenceClient` instance so that SDK-level rate limiting works correctly across all requests.
- Transfer safeguards (per-transfer limit, daily limit, audit trail) are enforced server-side. The client cannot bypass them.

## Telegram Bot Configuration

The bot splits configuration into two layers: secrets (environment variables) and non-secret settings (`bot-config.yaml`).

### Secrets (Environment Variables)

| Env Var | Required | Default | Description |
|---------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | -- | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `ANTHROPIC_API_KEY` | Yes | -- | Anthropic API key for the Claude agent |
| `BOT_CONFIG` | No | `BOT_DATA_DIR/bot-config.yaml` | Explicit path to config YAML file |
| `BOT_DATA_DIR` | No | `.` | Directory for bot data files (memories, daily limits, audit) |

Plus all SDK environment variables listed above (`SEQUENCE_EMAIL`, `SEQUENCE_PASSWORD`, `SEQUENCE_TOTP`, `SEQUENCE_ORG_ID`, `SEQUENCE_KYC_ID`, `SEQUENCE_AUTH0_CLIENT_ID`).

### Non-Secret Settings (bot-config.yaml)

The config file is required. The bot will not start without it.

**Config file resolution order:**

1. `BOT_CONFIG` env var -- explicit path
2. `BOT_DATA_DIR/bot-config.yaml` -- convention-based location

#### agent section

| Field | Default | Description |
|-------|---------|-------------|
| `model` | *(required)* | Claude model ID (e.g. `claude-opus-4-6`) |
| `max_tokens` | `1024` | Maximum tokens per Claude response |
| `max_history` | `50` | Maximum conversation messages before trimming |
| `trim_to` | `40` | Number of messages to keep after trimming (preserves first 10 + last N) |
| `conversation_ttl` | `3600` | Seconds of inactivity before conversation context resets |

#### safeguards section

| Field | Default | Description |
|-------|---------|-------------|
| `max_transfer_cents` | `1_000_000` | Per-transfer limit in cents ($10,000) |
| `max_daily_transfer_cents` | `2_500_000` | Per-user daily cumulative limit in cents ($25,000) |
| `pending_transfer_ttl` | `300` | Seconds before a staged transfer expires (5 minutes) |

#### telegram section

| Field | Default | Description |
|-------|---------|-------------|
| `group_id` | *(required)* | Telegram group ID where the bot operates |
| `users` | *(required)* | Map of Telegram user IDs (int) to display names (string). Acts as an allowlist. |
| `rate_limit_messages` | `10` | Maximum messages per sliding window |
| `rate_limit_window_seconds` | `60` | Sliding window duration in seconds |
| `max_message_length` | `2000` | User messages are truncated beyond this length |

#### memory section

| Field | Default | Description |
|-------|---------|-------------|
| `max_facts` | `100` | Maximum number of persistent facts the bot can store |

#### system_prompt

A top-level YAML key (not nested under any section). This is the base system prompt injected into every Claude API call. It defines the bot's personality, behavior rules, and instructions for tool usage. The bot appends the current date/time, user identity, and any stored memories to this prompt automatically.

### Full Example

```yaml
agent:
  model: claude-opus-4-6
  max_tokens: 1024
  max_history: 50
  trim_to: 40
  conversation_ttl: 3600

safeguards:
  max_transfer_cents: 1_000_000
  max_daily_transfer_cents: 2_500_000
  pending_transfer_ttl: 300

telegram:
  group_id: -100000000000
  users:
    12345: Alice
    67890: Bob
  rate_limit_messages: 10
  rate_limit_window_seconds: 60
  max_message_length: 2000

memory:
  max_facts: 100

system_prompt: |
  You are a personal finance assistant that helps manage a GetSequence account.
  Be concise -- this is Telegram.
```

## Data Files

All data files are written to `SEQUENCE_DATA_DIR` (SDK-level) or `BOT_DATA_DIR` (bot-level). In Docker deployments, both typically point to `/app/data` backed by a named volume.

| File | Created By | Description |
|------|------------|-------------|
| `.tokens.json` | SDK auth (`auth.py`) | Cached Auth0 access and refresh tokens. Automatically created on first login. Token lifetime is approximately 24 hours; refresh tokens are used automatically. |
| `.audit.jsonl` | Safeguards (`AuditLog`) | Append-only audit trail of transfer operations. Each line is a JSON object with timestamp, event type, user info, transfer details. Events: `transfer_staged`, `transfer_confirmed`, `transfer_cancelled`, `transfer_failed`, `transfer_expired`. |
| `.daily_limits.json` | Safeguards (`DailyLimitTracker`) | Daily transfer totals tracked per user (bot) or globally (API). Auto-prunes records older than 2 days. |
| `.memories.json` | Bot memory (`MemoryStore`) | Persistent facts for the AI agent's context. Array of fact objects with ID, content, author, and timestamps. |
| `bot-config.yaml` | User | Non-secret bot configuration. Bind-mounted read-only in Docker. |

### Docker Volume Layout

In Docker, the data directory `/app/data` contains all the files above. The compose files use a named volume for persistence:

```
/app/data/
  .tokens.json          # SDK auth tokens
  .audit.jsonl          # Audit trail
  .daily_limits.json    # Daily transfer limits
  .memories.json        # Bot memory (bot only)
  bot-config.yaml       # Config file (bind-mounted read-only)
```

## Configuration by Component

A quick reference of which configuration each component requires:

| Config | SDK | API Server | Bot |
|--------|-----|------------|-----|
| `SEQUENCE_EMAIL` | Yes | Yes | Yes |
| `SEQUENCE_PASSWORD` | Yes | Yes | Yes |
| `SEQUENCE_TOTP` | Yes | Yes | Yes |
| `SEQUENCE_ORG_ID` | Yes | Yes | Yes |
| `SEQUENCE_KYC_ID` | Yes | Yes | Yes |
| `SEQUENCE_AUTH0_CLIENT_ID` | Yes | Yes | Yes |
| `SEQUENCE_DATA_DIR` | Optional | Optional | Optional |
| `SEQUENCE_API_KEY` | -- | Yes | -- |
| `SEQUENCE_SERVER_HOST` | -- | Optional | -- |
| `SEQUENCE_SERVER_PORT` | -- | Optional | -- |
| `SEQUENCE_MAX_TRANSFER_CENTS` | -- | Optional | -- |
| `SEQUENCE_MAX_DAILY_TRANSFER_CENTS` | -- | Optional | -- |
| `TELEGRAM_BOT_TOKEN` | -- | -- | Yes |
| `ANTHROPIC_API_KEY` | -- | -- | Yes |
| `BOT_CONFIG` | -- | -- | Optional |
| `BOT_DATA_DIR` | -- | -- | Optional |
| `bot-config.yaml` | -- | -- | Yes |
