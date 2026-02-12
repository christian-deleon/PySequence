set quiet := true

op_account := "my.1password.com"
dc := "docker compose"
dc_dev := "docker compose -f compose.dev.yaml"

# List all available commands
[private]
default:
    just --list --unsorted

# ─── Helpers ──────────────────────────────────────────────────────────────────

# Run an op CLI command with the project account
[private]
op *args:
    op --account {{ op_account }} {{ args }}

# Run a command with 1Password secrets injected
[private]
oprun *args:
    just op run --env-file op.env -- {{ args }}

# Run docker compose with 1Password secrets injected
[private]
opdc *args:
    just oprun {{ dc }} {{ args }}

# Run docker compose (dev) with 1Password secrets injected
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

# ─── Services ────────────────────────────────────────────────────────────────

# Start the API server (--op for 1Password secrets)
[arg("op", long="op", value="true")]
up op="false" *args:
    {{ if op == "true" { "just opdc" } else { dc } }} up --build -d {{ args }}

# Stop the API server
down *args:
    {{ dc }} down {{ args }}

# Build Docker images
build:
    {{ dc }} build
    {{ dc_dev }} build

# Follow API server logs
logs:
    {{ dc }} logs -f

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
