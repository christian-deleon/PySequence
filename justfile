set quiet := true

op_account := "my.1password.com"
dc_api := "docker compose -f compose.api.yaml"
dc_bot := "docker compose -f compose.bot.yaml"
dc_dev := "docker compose -f compose.dev.yaml"

[private]
default:
    just --list --unsorted

# ─── Helpers ──────────────────────────────────────────────────────────────────

[private]
op *args:
    op --account {{ op_account }} {{ args }}

[private]
oprun *args:
    just op run --env-file op.env -- {{ args }}

[private]
opdc-api *args:
    just oprun {{ dc_api }} {{ args }}

[private]
opdc-bot *args:
    just oprun {{ dc_bot }} {{ args }}

[private]
opdc-dev *args:
    just oprun {{ dc_dev }} {{ args }}

# ─── Testing ──────────────────────────────────────────────────────────────────

# Run unit tests in Docker (--op for 1Password secrets)
[arg("op", long="op", value="true")]
test-unit op="false" *args:
    {{ if op == "true" { "just opdc-dev" } else { dc_dev } }} run --build --rm dev pytest {{ args }}

# Run integration tests in Docker (--op for 1Password secrets)
[arg("op", long="op", value="true")]
test-integration op="false" *args:
    {{ if op == "true" { "just opdc-dev" } else { dc_dev } }} run --build --rm dev pytest -x --timeout=120 -m integration {{ args }}

# Run all tests (unit + integration) in Docker (--op for 1Password secrets)
[arg("op", long="op", value="true")]
test-all op="false" *args:
    {{ if op == "true" { "just opdc-dev" } else { dc_dev } }} run --build --rm dev pytest --override-ini "addopts=--import-mode=importlib" {{ args }}

# ─── API Server ───────────────────────────────────────────────────────────────

# Start the API server (--op for 1Password secrets)
[arg("op", long="op", value="true")]
api-up op="false" *args:
    {{ if op == "true" { "just opdc-api" } else { dc_api } }} up --build -d {{ args }}

# Stop the API server
api-down *args:
    {{ dc_api }} down {{ args }}

# Follow API server logs
api-logs:
    {{ dc_api }} logs -f

# ─── Telegram Bot ─────────────────────────────────────────────────────────────

# Start the Telegram bot (--op for 1Password secrets)
[arg("op", long="op", value="true")]
bot-up op="false" *args:
    {{ if op == "true" { "just opdc-bot" } else { dc_bot } }} up --build -d {{ args }}

# Stop the Telegram bot
bot-down *args:
    {{ dc_bot }} down {{ args }}

# Follow Telegram bot logs
bot-logs:
    {{ dc_bot }} logs -f

# ─── Build ────────────────────────────────────────────────────────────────────

# Build all Docker images
build:
    {{ dc_api }} build
    {{ dc_bot }} build
    {{ dc_dev }} build

# Build the API server Docker image
api-build:
    {{ dc_api }} build

# Build the Telegram bot Docker image
bot-build:
    {{ dc_bot }} build

# Build the dev/test Docker image
dev-build:
    {{ dc_dev }} build

# ─── Maintenance ──────────────────────────────────────────────────────────────

# Install dependencies (for IDE support)
install:
    poetry install

# Force re-authentication (delete cached tokens)
[confirm("Delete .tokens.json and force re-authentication? (y/n)")]
reauth:
    rm -f .tokens.json

# Format code with Black
fmt:
    black .

# Get code statistics with cloc
loc:
    cloc --fmt=1 --thousands-delimiter=, --vcs=git .
