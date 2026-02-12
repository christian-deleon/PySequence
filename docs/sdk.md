# PySequence SDK

Core Python SDK for the [GetSequence](https://getsequence.io/) personal finance platform. Communicates with the Sequence GraphQL API using browser-compatible HTTP requests.

**Package:** `pysequence-sdk`
**Source:** [`packages/pysequence-sdk/`](https://github.com/christian-deleon/PySequence/tree/main/packages/pysequence-sdk)

## Quick Start

```python
from pysequence_sdk import SequenceClient, get_access_token

token = get_access_token()
with SequenceClient(token) as client:
    pods = client.get_pods()
    balance = client.get_total_balance()
```

For long-running use (servers, bots), pass a `token_provider` so the client auto-refreshes expired tokens before each request:

```python
client = SequenceClient(get_access_token(), token_provider=get_access_token)
```

## Auth Flow

`get_access_token()` is the main entry point for obtaining a valid access token. It handles the full lifecycle automatically:

1. **Check cache** -- Load `.tokens.json` from `SEQUENCE_DATA_DIR` (defaults to current directory).
2. **Return if valid** -- If the cached token has more than 60 seconds remaining, return it immediately.
3. **Refresh if expired** -- If a `refresh_token` is available, call the Auth0 `refresh_token` grant at `https://auth.getsequence.io/oauth/token`.
4. **Full re-authentication** -- If no tokens exist or the refresh fails, launch a headless Chromium browser via Playwright and perform the full Auth0 Universal Login flow (email, password, TOTP MFA).

**Key details:**

- Auth0 domain: `https://auth.getsequence.io`
- Application URL: `https://app.getsequence.io`
- Token lifetime: approximately 24 hours
- Tokens are cached to `.tokens.json` in the directory specified by `SEQUENCE_DATA_DIR`
- The browser login types credentials with per-character random delays and navigates through Auth0's multi-step flow (email -> password -> MFA)
- After login, the access token is extracted from the browser's `sessionStorage`

```python
from pysequence_sdk import get_access_token

# Handles caching, refresh, and re-auth automatically
token = get_access_token()
```

## Client API

### Initialization

```python
from pysequence_sdk import SequenceClient, get_access_token

# Basic usage
token = get_access_token()
client = SequenceClient(token)

# With auto-refresh for long-running processes
client = SequenceClient(get_access_token(), token_provider=get_access_token)

# As a context manager (auto-closes the session)
with SequenceClient(token) as client:
    pods = client.get_pods()
```

**Constructor parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `access_token` | `str` | A valid Auth0 access token |
| `token_provider` | `Callable[[], str] \| None` | Optional callable that returns a fresh token. Called before every request when provided. |

### Methods

#### `get_pods() -> list[dict]`

Return every pod with its current balance.

```python
pods = client.get_pods()
# [
#   {
#     "id": "pod-uuid",
#     "name": "Emergency Fund",
#     "organization_id": "org-uuid",
#     "balance_cents": 150000,
#     "balance": "$1,500.00"
#   },
#   ...
# ]
```

#### `get_total_balance() -> dict`

Return the total balance across all pods.

```python
total = client.get_total_balance()
# {
#   "total_balance_cents": 500000,
#   "total_balance": "$5,000.00",
#   "pod_count": 4
# }
```

#### `get_pod_balance(pod_name: str) -> dict | None`

Look up a single pod by name. Case-insensitive. Falls back to substring match if exactly one pod contains the search term. Returns `None` if no match is found.

```python
pod = client.get_pod_balance("emergency")
# {"id": "...", "name": "Emergency Fund", "organization_id": "...", "balance_cents": 150000, "balance": "$1,500.00"}

pod = client.get_pod_balance("nonexistent")
# None
```

#### `get_pod_detail(organization_id: str, pod_id: str) -> dict`

Get detailed pod information including recent transfers. Timestamps in the response are converted from UTC to Eastern time.

```python
detail = client.get_pod_detail("org-uuid", "pod-uuid")
```

#### `transfer(kyc_id, source_id, destination_id, amount_cents, ...) -> dict`

Transfer funds between pods, ports, or external accounts.

```python
result = client.transfer(
    kyc_id="kyc-uuid",
    source_id="source-pod-uuid",
    destination_id="dest-pod-uuid",
    amount_cents=500,  # $5.00
    source_type="POD",         # default
    destination_type="POD",    # default
    description="",            # optional ACH description
    instant=False,             # optional instant transfer
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `kyc_id` | `str` | -- | KYC application ID (required by the API) |
| `source_id` | `str` | -- | UUID of the source pod/port/account |
| `destination_id` | `str` | -- | UUID of the destination pod/port/account |
| `amount_cents` | `int` | -- | Amount in cents (e.g. 500 = $5.00) |
| `source_type` | `str` | `"POD"` | One of `"POD"`, `"PORT"`, `"ACCOUNT"` |
| `destination_type` | `str` | `"POD"` | One of `"POD"`, `"PORT"`, `"ACCOUNT"` |
| `description` | `str` | `""` | Optional ACH description |
| `instant` | `bool` | `False` | Whether to use instant transfer |

Raises `RuntimeError` if the transfer fails (e.g. insufficient funds).

#### `get_activity_summary() -> dict`

Return monthly activity summary.

```python
summary = client.get_activity_summary()
# {
#   "transfer_count": 12,
#   "rule_executions": 5,
#   "total_incoming_cents": 300000,
#   "total_incoming": "$3,000.00"
# }
```

#### `get_activity(org_id, ...) -> dict`

Return paginated transfer activity with optional filters.

```python
activity = client.get_activity(
    org_id="org-uuid",
    first=10,                    # page size (default 10)
    after="",                    # cursor for pagination
    date_start="2025-01-01",     # optional ISO date
    date_end="2025-01-31",       # optional ISO date
    statuses=["COMPLETE"],       # optional status filter
    directions=["INCOMING"],     # optional direction filter
    activity_types=["ACH"],      # optional activity type filter
    hide_internal=False,         # hide internal transfers
    name="",                     # search by name
)

# {
#   "transfers": [
#     {
#       "id": "transfer-uuid",
#       "type": "ONE_TIME_TRANSFER",
#       "status": "COMPLETE",
#       "error_reason": null,
#       "created_at": "2025-01-15T10:30:00-05:00",
#       "updated_at": "2025-01-15T10:31:00-05:00",
#       "amount_cents": 5000,
#       "amount": "$50.00",
#       "source": {...},
#       "destination": {...},
#       "direction": "INTERNAL",
#       "activity_type": "ONE_TIME_TRANSFER"
#     }
#   ],
#   "page_info": {
#     "end_cursor": "cursor-string",
#     "has_next_page": true
#   }
# }
```

#### `get_transfer_detail(org_id: str, transfer_id: str) -> dict`

Return full detail for a single transfer including status tracking. Supports both simple transfers (single payment) and compound transfers (pull + push payments).

```python
detail = client.get_transfer_detail("org-uuid", "transfer-uuid")
```

The response includes a `details` field with either:
- `{"type": "simple", "status": ..., "created_at": ..., "completed_at": ..., "expected_completion": ...}`
- `{"type": "compound", "pull": {...}, "push": {...}, "reversal": {...}}`

If the transfer was created by a rule, a `rule` field is included with `trigger_type` and `trigger_cron`.

#### `get_all_accounts(org_id: str | None = None) -> dict`

Return all account types: pods, ports, and external accounts. Optionally filter by organization ID.

```python
accounts = client.get_all_accounts()
# {
#   "pods": [{"id": "...", "name": "...", "type": "...", "balance_cents": ..., "balance": "..."}],
#   "ports": [{"id": "...", "name": "...", "balance_cents": ..., "balance": "..."}],
#   "accounts": [{"id": "...", "name": "...", "type": "...", "provider_type": "...", "institution": "...", "balance_cents": ..., "balance": "..."}]
# }
```

#### `close() -> None`

Close the underlying HTTP session. Called automatically when using the context manager.

```python
client.close()
```

### Low-Level Execution

The `execute()` method is available for running arbitrary GraphQL queries:

```python
data = client.execute(
    query="query { me { id } }",
    variables={"key": "value"},
    operation_name="MyQuery",
)
```

## HTTP Configuration

The SDK uses `curl_cffi` with Chrome TLS fingerprinting to ensure requests are indistinguishable from real browser traffic.

**What curl_cffi handles:**
- TLS fingerprint matching Chrome
- HTTP/2 SETTINGS and pseudo-header order
- User-Agent and standard browser headers

**Additional request headers sent with every GraphQL request:**
- `origin: https://app.getsequence.io`
- `referer: https://app.getsequence.io/`
- `sec-fetch-dest: empty`, `sec-fetch-mode: cors`, `sec-fetch-site: same-origin`
- `x-request-id: webapp-<uuid-v4>` (matches the webapp's request ID format)
- `accept: application/graphql-response+json, application/graphql+json, application/json, text/event-stream, multipart/mixed`
- `authorization: Bearer <token>`

**Rate limiting:**
- Minimum 1.5 seconds between any two requests
- Plus random 0-2 second jitter
- If enough wall-clock time has elapsed naturally, the delay is skipped

**GraphQL endpoint:** `POST https://app.getsequence.io/api/graphql`

## Safeguards

Shared by both the API server and the Telegram bot. Located in `pysequence_sdk.safeguards`.

### AuditLog

Append-only JSONL audit trail for financial operations. Writes one JSON line per event to `.audit.jsonl` in `SEQUENCE_DATA_DIR`.

```python
from pysequence_sdk.safeguards import AuditLog

audit = AuditLog()  # uses default path: SEQUENCE_DATA_DIR/.audit.jsonl

audit.log(
    "transfer_requested",
    user_id=12345,
    user_name="john",
    transfer_id="transfer-uuid",
    amount_cents=5000,
    source="source-pod-uuid",
    destination="dest-pod-uuid",
    note="Monthly savings transfer",
    error=None,
)
```

Each log entry is a JSON object with:
- `timestamp` -- UTC ISO-8601 timestamp
- `event_type` -- String describing the event (e.g. `"transfer_requested"`, `"transfer_completed"`, `"transfer_failed"`)
- Optional fields: `user_id`, `user_name`, `transfer_id`, `amount_cents`, `source`, `destination`, `note`, `error`

### DailyLimitTracker

JSON-backed daily transfer limit tracker. Persists to `.daily_limits.json` in `SEQUENCE_DATA_DIR`. Supports per-user and global limits. Automatically prunes records older than 2 days.

```python
from pysequence_sdk.safeguards import DailyLimitTracker

tracker = DailyLimitTracker(max_daily_cents=2_500_000)  # $25,000 daily limit

# Check if a transfer is within the daily limit
allowed, remaining = tracker.check(amount_cents=50000)
# allowed: True/False
# remaining: cents remaining in today's limit

# Check per-user limit
allowed, remaining = tracker.check(amount_cents=50000, user_id=12345)

# Record a completed transfer
tracker.record(amount_cents=50000, transfer_id="transfer-uuid")
tracker.record(amount_cents=50000, transfer_id="transfer-uuid", user_id=12345)
```

**Storage format:** Nested dictionary keyed by date and user. When `user_id` is omitted, a `"__global__"` key is used.

## Models (Pydantic)

Response models defined in `pysequence_sdk.models`:

| Model | Fields |
|-------|--------|
| `Pod` | `id`, `name`, `organization_id`, `balance_cents`, `balance` |
| `Port` | `id`, `name`, `organization_id`, `balance_cents`, `balance` |
| `ExternalAccount` | `id`, `name`, `organization_id`, `balance_cents`, `balance` |
| `TotalBalance` | `total_balance_cents`, `total_balance`, `pod_count` |
| `TransferParty` | `name` |
| `Transfer` | `id`, `status`, `amount`, `amount_cents`, `source` (TransferParty), `destination` (TransferParty), `direction`, `activity_type`, `created_at` |
| `PageInfo` | `end_cursor`, `has_next_page` |
| `ActivityPage` | `transfers` (list[Transfer]), `page_info` (PageInfo) |
| `ActivitySummary` | `transfer_count`, `rule_executions`, `total_incoming_cents`, `total_incoming` |
| `AllAccounts` | `pods` (list[Pod]), `ports` (list[Port]), `accounts` (list[ExternalAccount]) |

## Types (Enums)

All enums use `StrEnum` and are defined in `pysequence_sdk.types`:

### TransferStatus

| Value | Description |
|-------|-------------|
| `PENDING` | Transfer has been created but not yet started |
| `PROCESSING` | Transfer is in progress |
| `COMPLETE` | Transfer completed successfully |
| `FAILED` | Transfer failed |
| `CANCELLED` | Transfer was cancelled |

### Direction

| Value | Description |
|-------|-------------|
| `INTERNAL` | Between pods within the same organization |
| `INCOMING` | Funds coming into the organization |
| `OUTGOING` | Funds leaving the organization |

### ActivityType

| Value | Description |
|-------|-------------|
| `ONE_TIME_TRANSFER` | Manual one-time transfer |
| `RULE` | Automated rule-based transfer |
| `DIRECT_DEPOSIT` | Direct deposit |
| `ACH` | ACH transfer |

### AccountType

| Value | Description |
|-------|-------------|
| `POD` | A Sequence pod (internal account) |
| `PORT` | A Sequence port (connected bank account) |
| `ACCOUNT` | An external account |

## Exceptions

All SDK exceptions inherit from `SequenceError`. Defined in `pysequence_sdk.exceptions`:

### SequenceError

Base exception for all SDK errors.

### AuthenticationError

Raised when authentication with GetSequence fails (browser login or token exchange).

### GraphQLError

Raised when the GraphQL API returns errors.

```python
from pysequence_sdk import GraphQLError

try:
    data = client.execute(query)
except GraphQLError as e:
    print(e.errors)  # list[dict] -- raw GraphQL error objects
    print(e.query)   # str -- the query that caused the error
```

### TokenExpiredError

Raised when the access token has expired and the refresh attempt failed.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SEQUENCE_EMAIL` | Yes | -- | Login email for GetSequence |
| `SEQUENCE_PASSWORD` | Yes | -- | Login password |
| `SEQUENCE_TOTP` | Yes | -- | Current TOTP code for MFA |
| `SEQUENCE_ORG_ID` | Yes | -- | Organization ID |
| `SEQUENCE_KYC_ID` | Yes | -- | KYC application ID |
| `SEQUENCE_AUTH0_CLIENT_ID` | Yes | -- | Auth0 client ID for token refresh |
| `SEQUENCE_DATA_DIR` | No | `.` | Directory for data files (`.tokens.json`, `.audit.jsonl`, `.daily_limits.json`) |
