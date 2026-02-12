# Telegram Bot

AI-powered Telegram bot that uses the [PySequence SDK](https://github.com/christian-deleon/PySequence) directly (not through the API server) with a Claude AI agent for natural language interactions. Users can check pod balances, transfer money, and manage memories through conversation.

The bot is an independently deployable component of the PySequence monorepo. It has its own Docker Compose file, its own safeguards (daily limits, audit trail, transfer confirmation), and a deliberately limited toolset.

## Setup

### Prerequisites

- **Telegram Bot Token** -- Create a bot via [@BotFather](https://t.me/BotFather)
- **Anthropic API key** -- For the Claude AI agent
- **GetSequence account credentials** -- Email, password, TOTP secret, org ID, KYC ID, Auth0 client ID

### Quick Start

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) and save the token.

2. Copy `bot-config.yaml` from the repo root and configure it:
   - `telegram.group_id`: Your Telegram group ID (the bot also works in DMs)
   - `telegram.users`: Map of Telegram user IDs to display names (acts as an allowlist)
   - `agent.model`: Claude model to use (e.g. `claude-opus-4-6`)
   - `system_prompt`: Customize the bot's personality and behavior rules

3. Set environment variables for secrets:
   ```bash
   export TELEGRAM_BOT_TOKEN="your-bot-token"
   export ANTHROPIC_API_KEY="your-anthropic-key"
   export SEQUENCE_EMAIL="your-email"
   export SEQUENCE_PASSWORD="your-password"
   export SEQUENCE_TOTP="your-totp-secret"
   export SEQUENCE_ORG_ID="your-org-id"
   export SEQUENCE_KYC_ID="your-kyc-id"
   export SEQUENCE_AUTH0_CLIENT_ID="your-auth0-client-id"
   ```

4. Run with Docker Compose:
   ```bash
   docker compose -f compose.bot.yaml up -d
   # Or with justfile:
   just bot-up
   ```

## bot-config.yaml Reference

All non-secret configuration lives in this file. Secrets (`TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`, `SEQUENCE_*`) always come from environment variables.

```yaml
agent:
  model: claude-opus-4-6        # Claude model ID (required)
  max_tokens: 1024              # Max tokens per response
  max_history: 50               # Max conversation messages before trimming
  trim_to: 40                   # Trim to this many messages when limit is hit
  conversation_ttl: 3600        # Reset conversation context after this many seconds of inactivity

safeguards:
  max_transfer_cents: 1_000_000        # $10,000 per-transfer limit
  max_daily_transfer_cents: 2_500_000  # $25,000 daily limit (per user)
  pending_transfer_ttl: 300            # 5 minutes to confirm a staged transfer

telegram:
  group_id: -100000000000       # Your Telegram group ID (required)
  users:                        # Allowed user IDs and display names (required)
    12345: Alice
    67890: Bob
  rate_limit_messages: 10       # Max messages per sliding window
  rate_limit_window_seconds: 60 # Sliding window duration in seconds
  max_message_length: 2000      # Truncate user messages beyond this length

memory:
  max_facts: 100                # Maximum persistent facts the bot can store

system_prompt: |
  Your custom system prompt here...
```

### Config File Resolution Order

1. `BOT_CONFIG` env var -- explicit path to the config file
2. `BOT_DATA_DIR/bot-config.yaml` -- convention-based location
3. If neither is found, the bot will not start (the config file is required)

### Required Fields

The following fields must be present in the config file or the bot will refuse to start:

- `agent.model` -- Claude model ID
- `system_prompt` -- The system prompt for the AI agent
- `telegram.group_id` -- Telegram group ID
- `telegram.users` -- At least one user ID mapping

## AI Tools

The bot's Claude agent has access to the following tools for interacting with the Sequence SDK:

| Tool | Description |
|------|-------------|
| `get_all_pods` | List all pods with balances |
| `get_total_balance` | Total balance across all pods |
| `get_pod_balance` | Single pod balance by name (case-insensitive, supports fuzzy matching) |
| `get_pod_detail` | Detailed pod info including bank details and recent transfers |
| `request_transfer` | Stage a transfer between pods (requires user confirmation via buttons) |
| `cancel_transfer` | Cancel a pending transfer |
| `get_recent_activity` | Recent transfers with optional filters (direction, status, activity_type) |
| `get_transfer_status` | Detailed status of a specific transfer by ID |
| `get_activity_summary` | Monthly activity summary (transfer count, rule executions, incoming funds) |
| `get_all_accounts` | All accounts: pods, ports (income sources), and external accounts |
| `save_memory` | Save or update a persistent fact (pass `fact_id` to update in place) |
| `delete_memory` | Delete a persistent fact by ID |
| `list_memories` | List all stored facts |

### Pod Name Resolution

Tools that accept pod names (`get_pod_balance`, `request_transfer`) use fuzzy matching:

1. Exact match (case-insensitive)
2. Single substring match -- if exactly one pod name contains the input as a substring
3. If no match or multiple matches, the tool returns an error with suggestions

## Transfer Flow

Transfers go through a staged confirmation flow to prevent accidental money movement:

1. **User requests a transfer** in natural language (e.g., "Move $50 from Savings to Groceries").
2. **Bot validates the request:**
   - Resolves pod names (fuzzy matching)
   - Checks source pod has sufficient balance
   - Checks per-transfer limit (`safeguards.max_transfer_cents`)
   - Checks per-user daily cumulative limit (`safeguards.max_daily_transfer_cents`)
   - Infers a transfer note from conversation context
3. **Bot stages the transfer** and sends a message with inline **Confirm** and **Cancel** buttons.
4. **User clicks Confirm** -- the transfer executes via the SDK and the daily limit is recorded.
5. **User clicks Cancel** -- the transfer is cancelled and logged in the audit trail.
6. **Transfers expire** after `pending_transfer_ttl` seconds (default: 5 minutes). Expired transfers cannot be confirmed.

### Ownership

Users can only confirm or cancel their own transfers. If user A stages a transfer, user B cannot click the buttons to confirm or cancel it.

## Memory System

The bot has a persistent memory store backed by `.memories.json` on disk.

- Facts survive bot restarts
- All stored facts are injected into the system prompt as context on every message
- Maximum number of facts is configurable (`memory.max_facts`, default: 100)
- When memory is full, the bot will tell the user and ask which facts to delete

### Operations

- **Save**: Create a new fact or update an existing one by passing its `fact_id`
- **Delete**: Remove a fact by ID
- **List**: Show all stored facts with their IDs

### Common Use Cases

- Pod nicknames (e.g., "The user calls the 'Emergency Fund' pod 'rainy day'")
- Spending patterns (e.g., "User typically spends $60-80 on gas")
- Transfer source preferences (e.g., "User prefers to transfer grocery money from Main")
- User preferences (e.g., "User gets paid on Fridays")

### Prompt Injection Protection

Memory contents are wrapped in clearly delimited markers in the system prompt and the agent is instructed to treat them as data only, never following instructions found within memories.

## Safeguards

The bot enforces multiple layers of safety since it moves real money:

| Safeguard | Description |
|-----------|-------------|
| **Per-transfer limit** | Rejects transfers above the configured maximum (default: $10,000). Configurable via `safeguards.max_transfer_cents`. |
| **Per-user daily limit** | Tracks cumulative daily transfer totals per user. Rejects when the limit is exceeded (default: $25,000). Configurable via `safeguards.max_daily_transfer_cents`. |
| **Transfer confirmation** | Every transfer must be explicitly confirmed via inline buttons. No transfer executes from conversation alone. |
| **Transfer expiry** | Staged transfers expire after `pending_transfer_ttl` seconds (default: 5 minutes). |
| **Audit trail** | Every transfer operation (staged, confirmed, cancelled, failed, expired) is logged to `.audit.jsonl`. |
| **Rate limiting** | Per-user sliding window rate limiter. Configurable via `telegram.rate_limit_messages` and `telegram.rate_limit_window_seconds`. |
| **Input length cap** | User messages are truncated to `telegram.max_message_length` characters (default: 2000). |
| **User allowlist** | Only Telegram user IDs listed in `telegram.users` can interact with the bot. |
| **Group restriction** | The bot only responds in the configured group (`telegram.group_id`) and in direct messages with allowed users. |
| **Ownership check** | Users can only confirm or cancel their own staged transfers. |

## Environment Variables

### Bot-Specific

| Var | Required | Default | Description |
|-----|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | -- | Telegram bot token from @BotFather |
| `ANTHROPIC_API_KEY` | Yes | -- | Anthropic API key for the Claude agent |
| `BOT_CONFIG` | No | `BOT_DATA_DIR/bot-config.yaml` | Explicit path to config YAML |
| `BOT_DATA_DIR` | No | `.` | Directory for bot data files (memories, daily limits, audit) |

### SDK (Also Required)

| Var | Required | Default | Description |
|-----|----------|---------|-------------|
| `SEQUENCE_EMAIL` | Yes | -- | Login email for GetSequence |
| `SEQUENCE_PASSWORD` | Yes | -- | Login password |
| `SEQUENCE_TOTP` | Yes | -- | TOTP secret for MFA |
| `SEQUENCE_ORG_ID` | Yes | -- | Organization ID |
| `SEQUENCE_KYC_ID` | Yes | -- | KYC application ID |
| `SEQUENCE_AUTH0_CLIENT_ID` | Yes | -- | Auth0 client ID |
| `SEQUENCE_DATA_DIR` | No | `.` | Directory for SDK data files (tokens) |

## Docker Deployment

The bot uses `compose.bot.yaml` at the repo root:

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

### Key Points

- `bot-config.yaml` is bind-mounted read-only into the container. Edit the host copy and restart the bot to apply changes.
- `bot-data` is a named volume that persists `.memories.json`, `.daily_limits.json`, `.audit.jsonl`, and `.tokens.json` across restarts.
- Both `BOT_DATA_DIR` and `SEQUENCE_DATA_DIR` point to `/app/data` so all data files are stored in the same persistent volume.
- Secrets are passed as environment variables (not baked into the image).

### Management Commands

```bash
just bot-up               # Start the bot
just bot-down             # Stop the bot
just bot-logs             # Follow bot logs
```

## Architecture

```
User (Telegram) --> telegram/bot.py --> ai/agent.py --> Claude API
                                             |
                                             v
                                        ai/tools.py --> SequenceClient (SDK) --> Sequence GraphQL API
                                             |
                                             v
                                        ai/memory.py --> .memories.json
                                             |
                                             v
                                     safeguards/ --> .audit.jsonl, .daily_limits.json
```

- `telegram/bot.py` -- Telegram handlers, rate limiting, inline button callbacks, transfer confirmation execution
- `ai/agent.py` -- Claude tool-use loop with conversation history management and TTL-based context reset
- `ai/tools.py` -- Tool definitions and execution (validation, pod lookup, staging, SDK calls)
- `ai/memory.py` -- Persistent JSON-backed fact store
- `config.py` -- YAML config loading, env var secrets, dataclass configs
