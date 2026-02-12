# PySequence API Server

FastAPI REST server wrapping the PySequence SDK. Acts as a trust boundary for external services (e.g. OpenClaw) that should not have direct SDK access. Provides API-key authentication and financial safeguards (per-transfer limits, daily limits, audit trail).

**Package:** `pysequence-api`
**Source:** [`packages/pysequence-api/`](https://github.com/christian-deleon/PySequence/tree/main/packages/pysequence-api)

## Architecture

The server maintains a single `SequenceClient` instance shared across all requests, ensuring rate limiting works correctly. On startup, it authenticates with GetSequence, initializes the daily limit tracker and audit log, and begins serving requests.

```
External Service  -->  [X-API-Key auth]  -->  API Server  -->  SequenceClient  -->  GraphQL API
                                                   |
                                              Safeguards
                                           (limits + audit)
```

## Authentication

All routes except `/api/health` require the `X-API-Key` header. The key is validated using constant-time comparison (`secrets.compare_digest`) to prevent timing attacks.

```bash
curl -H "X-API-Key: your-key" http://localhost:8720/api/pods
```

Requests with a missing or invalid API key receive a `401 Unauthorized` response:

```json
{"detail": "Invalid API key"}
```

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | No | Health check |
| GET | `/api/pods` | Yes | List all pods with balances |
| GET | `/api/pods/balance` | Yes | Total balance across all pods |
| GET | `/api/pods/{pod_name}/balance` | Yes | Single pod balance by name |
| GET | `/api/pods/detail/{pod_id}` | Yes | Pod detail (uses default org_id) |
| GET | `/api/pods/{org_id}/{pod_id}` | Yes | Pod detail with explicit org_id |
| GET | `/api/accounts` | Yes | All accounts (pods, ports, external) |
| GET | `/api/activity/summary` | Yes | Monthly activity summary |
| GET | `/api/activity` | Yes | Paginated transfer activity |
| GET | `/api/transfers/{transfer_id}` | Yes | Single transfer detail |
| GET | `/api/activity/{org_id}/{transfer_id}` | Yes | Transfer detail with explicit org_id |
| POST | `/api/transfers` | Yes | Transfer funds (with safeguards) |

### GET /api/health

Health check endpoint. No authentication required.

```bash
curl http://localhost:8720/api/health
```

### GET /api/pods

List all pods with current balances.

```bash
curl -H "X-API-Key: $KEY" http://localhost:8720/api/pods
```

```json
[
  {
    "id": "pod-uuid",
    "name": "Emergency Fund",
    "organization_id": "org-uuid",
    "balance_cents": 150000,
    "balance": "$1,500.00"
  }
]
```

### GET /api/pods/balance

Total balance across all pods.

```bash
curl -H "X-API-Key: $KEY" http://localhost:8720/api/pods/balance
```

```json
{
  "total_balance_cents": 500000,
  "total_balance": "$5,000.00",
  "pod_count": 4
}
```

### GET /api/pods/{pod_name}/balance

Single pod balance by name (case-insensitive, substring fallback).

```bash
curl -H "X-API-Key: $KEY" http://localhost:8720/api/pods/emergency/balance
```

Returns 404 if no matching pod is found.

### GET /api/pods/detail/{pod_id}

Pod detail including recent transfers. Uses the server's default `SEQUENCE_ORG_ID`.

```bash
curl -H "X-API-Key: $KEY" http://localhost:8720/api/pods/detail/pod-uuid
```

### GET /api/pods/{org_id}/{pod_id}

Pod detail with an explicit organization ID.

```bash
curl -H "X-API-Key: $KEY" http://localhost:8720/api/pods/org-uuid/pod-uuid
```

### GET /api/accounts

All account types (pods, ports, external accounts).

```bash
curl -H "X-API-Key: $KEY" http://localhost:8720/api/accounts
```

```json
{
  "pods": [...],
  "ports": [...],
  "accounts": [...]
}
```

### GET /api/activity/summary

Monthly activity summary.

```bash
curl -H "X-API-Key: $KEY" http://localhost:8720/api/activity/summary
```

```json
{
  "transfer_count": 12,
  "rule_executions": 5,
  "total_incoming_cents": 300000,
  "total_incoming": "$3,000.00"
}
```

### GET /api/activity

Paginated transfer activity. Supports query parameters for filtering.

```bash
curl -H "X-API-Key: $KEY" "http://localhost:8720/api/activity?first=10&statuses=COMPLETE&directions=INCOMING"
```

### GET /api/transfers/{transfer_id}

Full transfer detail with status tracking. Uses the server's default `SEQUENCE_ORG_ID`.

```bash
curl -H "X-API-Key: $KEY" http://localhost:8720/api/transfers/transfer-uuid
```

### GET /api/activity/{org_id}/{transfer_id}

Transfer detail with an explicit organization ID.

```bash
curl -H "X-API-Key: $KEY" http://localhost:8720/api/activity/org-uuid/transfer-uuid
```

### POST /api/transfers

Transfer funds between pods, ports, or external accounts. Subject to per-transfer and daily limits. All transfer attempts are logged to the audit trail.

```bash
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  http://localhost:8720/api/transfers \
  -d '{
    "source_id": "source-pod-uuid",
    "destination_id": "dest-pod-uuid",
    "amount_cents": 5000
  }'
```

**Request body:**

```json
{
  "source_id": "uuid",
  "destination_id": "uuid",
  "amount_cents": 5000,
  "source_type": "POD",
  "destination_type": "POD",
  "description": "",
  "instant": false,
  "kyc_id": null
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source_id` | `str` | -- | UUID of the source pod/port/account (required) |
| `destination_id` | `str` | -- | UUID of the destination pod/port/account (required) |
| `amount_cents` | `int` | -- | Amount in cents, must be > 0 (required) |
| `source_type` | `str` | `"POD"` | One of `"POD"`, `"PORT"`, `"ACCOUNT"` |
| `destination_type` | `str` | `"POD"` | One of `"POD"`, `"PORT"`, `"ACCOUNT"` |
| `description` | `str` | `""` | Optional ACH description |
| `instant` | `bool` | `false` | Whether to use instant transfer |
| `kyc_id` | `str \| null` | `null` | KYC ID override (defaults to server's `SEQUENCE_KYC_ID`) |

**Error responses:**

- `400` -- Amount exceeds per-transfer limit, daily limit exceeded, or transfer failed at the API level
- `401` -- Invalid or missing API key
- `502` -- Upstream GraphQL error

## Transfer Safeguards

Every transfer through the API server passes through three layers of protection:

### Per-Transfer Limit

Rejects any single transfer exceeding the configured maximum. Default: **$10,000** (1,000,000 cents).

```
400 Bad Request
{"detail": "Amount 1500000 cents exceeds per-transfer limit of 1000000 cents"}
```

Configure via `SEQUENCE_MAX_TRANSFER_CENTS`.

### Daily Limit

Tracks cumulative transfer totals per day. Rejects transfers that would push the daily total over the limit. Default: **$25,000** (2,500,000 cents).

```
400 Bad Request
{"detail": "Amount 500000 cents exceeds daily remaining limit of 200000 cents"}
```

Daily totals are persisted to `.daily_limits.json` in `SEQUENCE_DATA_DIR` and automatically pruned after 2 days. Configure via `SEQUENCE_MAX_DAILY_TRANSFER_CENTS`.

### Audit Trail

Every transfer attempt is logged to `.audit.jsonl` in `SEQUENCE_DATA_DIR` with:
- `transfer_requested` -- logged before the transfer is attempted
- `transfer_completed` -- logged after a successful transfer (includes the `transfer_id`)
- `transfer_failed` -- logged when a transfer fails (includes the error message)

Each entry includes a UTC timestamp, event type, amount, source, and destination.

## Deployment

### Docker Compose

The API server uses `compose.api.yaml` at the repository root:

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

The `data` volume persists token cache, audit logs, and daily limit records across container restarts.

### Justfile Commands

```bash
# Start the API server
just api-up

# Stop the API server
just api-down

# Follow API server logs
just api-logs
```

### Build

The API server uses the `prod` target in the multi-stage `Dockerfile` at the repository root:

```bash
# Build all Docker images
just build
```

## Environment Variables

### Server-Specific Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SEQUENCE_API_KEY` | Yes | -- | API key for authenticating incoming requests |
| `SEQUENCE_SERVER_HOST` | No | `0.0.0.0` | Server bind host |
| `SEQUENCE_SERVER_PORT` | No | `8720` | Server bind port |
| `SEQUENCE_MAX_TRANSFER_CENTS` | No | `1000000` | Per-transfer limit in cents ($10,000) |
| `SEQUENCE_MAX_DAILY_TRANSFER_CENTS` | No | `2500000` | Daily cumulative transfer limit in cents ($25,000) |

### SDK Variables (also required)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SEQUENCE_EMAIL` | Yes | -- | Login email for GetSequence |
| `SEQUENCE_PASSWORD` | Yes | -- | Login password |
| `SEQUENCE_TOTP` | Yes | -- | Current TOTP code for MFA |
| `SEQUENCE_ORG_ID` | Yes | -- | Organization ID (also used as default for routes) |
| `SEQUENCE_KYC_ID` | Yes | -- | KYC application ID (used as default for transfers) |
| `SEQUENCE_AUTH0_CLIENT_ID` | Yes | -- | Auth0 client ID for token refresh |
| `SEQUENCE_DATA_DIR` | No | `.` | Directory for data files |

## Error Handling

The API server maps errors to appropriate HTTP status codes:

| Error | Status Code | Description |
|-------|-------------|-------------|
| Invalid/missing API key | 401 | Authentication failure |
| Transfer limit exceeded | 400 | Safeguard rejection |
| Transfer failed at Sequence | 400 | Upstream transfer error |
| GraphQL/network error | 502 | Upstream communication failure |
| Pod not found | 404 | Resource not found |

All `RuntimeError` exceptions from the SDK are caught and returned as `502` responses with the error message in the `detail` field.
