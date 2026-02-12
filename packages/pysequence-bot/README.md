# pysequence-bot

AI-powered Telegram bot for the [GetSequence](https://getsequence.io/) personal finance platform. Uses Claude to provide natural language interactions for checking balances and transferring money.

## Quick Start

```bash
# 1. Configure bot-config.yaml with your group ID and user mappings
# 2. Set environment variables
# 3. Start the bot
docker compose -f compose.bot.yaml up -d
# Or with justfile:
just bot-up
```

## Features

- Natural language finance queries via Claude AI
- Pod balance checking and comparison
- Fund transfers with confirmation buttons
- Persistent memory for preferences and patterns
- Per-user rate limiting and daily transfer limits
- Audit trail for all transfer operations
- Configurable system prompt and personality

## Configuration

Non-secret configuration (model, limits, rate limits, system prompt, user mappings) lives in `bot-config.yaml` at the repo root. Copy it, edit it, and mount it into Docker -- no code changes needed.

Secrets are always set via environment variables:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `SEQUENCE_EMAIL` | Sequence login email |
| `SEQUENCE_PASSWORD` | Sequence login password |
| `SEQUENCE_TOTP` | Current TOTP code |
| `SEQUENCE_ORG_ID` | Organization ID |
| `SEQUENCE_KYC_ID` | KYC ID |
| `SEQUENCE_AUTH0_CLIENT_ID` | Auth0 client ID |

## Requirements

- Python >= 3.11

## Documentation

[Full documentation](https://github.com/christian-deleon/PySequence/blob/main/docs/telegram-bot.md)

## License

[MIT](https://github.com/christian-deleon/PySequence/blob/main/LICENSE)
