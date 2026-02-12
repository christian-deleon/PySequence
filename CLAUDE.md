# PySequence

Unofficial Python SDK and REST API server for the [GetSequence](https://getsequence.io/) personal finance platform.

## Monorepo Structure

```
packages/
  pysequence-sdk/        # GraphQL SDK (curl_cffi + Playwright)
  pysequence-api/        # FastAPI REST server (depends on SDK)
  pysequence-client/     # HTTP client for the REST server (standalone)
```

**Dependency graph:**
```
pysequence-client → (HTTP) → pysequence-api → pysequence-sdk → (GraphQL) → Sequence.io
```

## Packages

### pysequence-sdk
Core SDK that communicates with the Sequence GraphQL API.

- `auth.py` — Auth0 token management (Playwright browser login + refresh + caching)
- `client.py` — `SequenceClient` GraphQL HTTP client
- `config.py` — `SequenceCredentials`, `SequenceConfig`, env var loading
- `models.py` — Pydantic response models (Pod, Transfer, etc.)
- `types.py` — Enums (TransferStatus, Direction, etc.)
- `exceptions.py` — SDK error types
- `graphql/queries.py` — GraphQL query strings
- `graphql/mutations.py` — GraphQL mutation strings

### pysequence-api
FastAPI REST server wrapping the SDK with financial safeguards.

- `app.py` — App factory with lifespan
- `config.py` — `ServerConfig`, env var loading
- `dependencies.py` — API key auth, shared client
- `models.py` — Pydantic request models
- `routes/` — Route modules (health, pods, accounts, activity, transfers)
- `safeguards/` — Audit trail + daily transfer limits

### pysequence-client
Standalone HTTP client for consuming the REST API. No SDK dependency.

- `client.py` — `SequenceApiClient`
- `models.py` — Response models
- `exceptions.py` — `ApiError`

## SDK Usage

```python
from pysequence_sdk import SequenceClient, get_access_token

token = get_access_token()
with SequenceClient(token) as client:
    pods = client.get_pods()
    balance = client.get_total_balance()
    detail = client.get_pod_detail(org_id, pod_id)
    result = client.transfer(kyc_id, source_id, dest_id, amount_cents=500)
```

For long-running use, pass a `token_provider` to auto-refresh expired tokens:

```python
client = SequenceClient(get_access_token(), token_provider=get_access_token)
```

## API Server Endpoints

All routes except `/api/health` require `X-API-Key` header.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (no auth) |
| GET | `/api/pods` | List all pods with balances |
| GET | `/api/pods/balance` | Total balance across all pods |
| GET | `/api/pods/{pod_name}/balance` | Single pod balance by name |
| GET | `/api/pods/detail/{pod_id}` | Pod detail (uses default org_id) |
| GET | `/api/pods/{org_id}/{pod_id}` | Pod detail with explicit org_id |
| GET | `/api/accounts` | All accounts (pods, ports, external) |
| GET | `/api/activity/summary` | Monthly activity summary |
| GET | `/api/activity` | Paginated transfer activity |
| GET | `/api/transfers/{transfer_id}` | Single transfer detail |
| GET | `/api/activity/{org_id}/{transfer_id}` | Transfer detail with explicit org_id |
| POST | `/api/transfers` | Transfer funds (with safeguards) |

### Transfer Safeguards

- **Per-transfer limit** — rejects transfers above `$10,000` (configurable)
- **Global daily limit** — rejects when cumulative daily total exceeds `$25,000` (configurable)
- **Audit trail** — every transfer attempt logged to `.audit.jsonl`

## HTTP Client Configuration

The SDK uses `curl_cffi` with Chrome configuration for browser-compatible HTTP requests. This ensures proper TLS fingerprinting and HTTP/2 behavior when communicating with the GraphQL API.

**What curl_cffi handles:**
- TLS fingerprint matching Chrome
- HTTP/2 SETTINGS and pseudo-header order
- User-Agent and standard browser headers

**Additional request headers:**
- `origin`, `referer`, `sec-fetch-*` headers matching browser XHR behavior
- `x-request-id: webapp-<uuid-v4>` matching the webapp's request ID format
- `accept` header matching the webapp's GraphQL accept string
- Rate limiting between requests

## Configuration

| Env Var | Required | Default | Description |
|---|---|---|---|
| `SEQUENCE_EMAIL` | Yes | — | Login email |
| `SEQUENCE_PASSWORD` | Yes | — | Login password |
| `SEQUENCE_TOTP` | Yes | — | Current TOTP code |
| `SEQUENCE_ORG_ID` | Yes | — | Organization ID |
| `SEQUENCE_KYC_ID` | Yes | — | KYC ID |
| `SEQUENCE_AUTH0_CLIENT_ID` | Yes | — | Auth0 client ID |
| `SEQUENCE_API_KEY` | Server | — | API key for server authentication |
| `SEQUENCE_DATA_DIR` | No | `.` | Directory for data files (.tokens.json, etc.) |
| `SEQUENCE_SERVER_HOST` | No | `0.0.0.0` | Server bind host |
| `SEQUENCE_SERVER_PORT` | No | `8720` | Server bind port |
| `SEQUENCE_MAX_TRANSFER_CENTS` | No | `1000000` | Per-transfer limit ($10,000) |
| `SEQUENCE_MAX_DAILY_TRANSFER_CENTS` | No | `2500000` | Daily transfer limit ($25,000) |

## API Details

- **Endpoint:** `POST https://app.getsequence.io/api/graphql`
- **Auth:** Bearer token from Auth0 (domain: `auth.getsequence.io`)
- **Token lifetime:** ~24 hours
- **Token management:** Automated via `get_access_token()`

## Auth0 Token Flow

Token management is fully automated via `auth.py`. Consumers just call `get_access_token()`.

1. Check `.tokens.json` for a cached token
2. If valid → return immediately
3. If expired but refresh token exists → use `refresh_token` grant
4. If no tokens or refresh fails → full re-authentication via Playwright browser login

## Development

Use `@justfile` recipes for common operations. Run `just` to see available recipes.

```bash
just test-unit            # Run unit tests in Docker
just test-integration     # Run integration tests in Docker
just test-all             # Run all tests (unit + integration) in Docker
just up                   # Start the API server
just down                 # Stop the API server
just build                # Build Docker images
just install              # Install dependencies (for IDE support)
just reauth               # Delete cached tokens to force re-authentication
just fmt                  # Format code with Black
```

All tests and the API server run in Docker. Add `--op` to any recipe to inject secrets via 1Password:

```bash
just test-unit --op       # Unit tests with 1Password secrets
just up --op              # Start API server with 1Password secrets
```

## Docker

All Docker files live at the project root: `Dockerfile`, `compose.yaml`, `compose.dev.yaml`.

Multi-stage build: `prod` (server entrypoint) and `dev` (includes tests).

## Requirements & Constraints

- **Real money — production quality:** This service moves real money. Correctness, reliability, and safety are non-negotiable.
- **Browser-compatible requests:** HTTP requests must use browser-compatible TLS and header configurations.
- **Not over-engineered:** Only build what's needed.
- **GraphQL queries must exactly match the webapp:** Query strings, fragment names, field selections, and `__typename` inclusions must match.
- **Use Justfile recipes:** Use `@justfile` recipes instead of raw `poetry run` commands when a recipe exists.
- **Single SequenceClient per server:** All requests share one instance so rate limiting works correctly.
- **Safeguards at server level only:** The SDK remains a thin GraphQL wrapper. The API server enforces limits.
