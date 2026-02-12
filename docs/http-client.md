# PySequence HTTP Client

Standalone HTTP client for consuming the PySequence REST API server. No SDK dependency -- only requires `httpx`. Use this package when you want to talk to the API server from a separate service without pulling in the full SDK and its browser dependencies.

**Package:** `pysequence-client`
**Source:** [`packages/pysequence-client/`](https://github.com/christian-deleon/PySequence/tree/main/packages/pysequence-client)

## Installation

```bash
pip install pysequence-client
```

## Quick Start

```python
from pysequence_client import SequenceApiClient

client = SequenceApiClient(
    base_url="http://localhost:8720",
    api_key="your-api-key",
)

# List all pods
pods = client.get_pods()

# Check total balance
balance = client.get_total_balance()

# Transfer funds
result = client.transfer(
    source_id="source-pod-uuid",
    destination_id="dest-pod-uuid",
    amount_cents=500,  # $5.00
)

# Clean up
client.close()
```

## Constructor

```python
SequenceApiClient(base_url: str, api_key: str, timeout: float = 30.0)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | -- | Base URL of the API server (e.g. `"http://localhost:8720"`) |
| `api_key` | `str` | -- | API key sent as the `X-API-Key` header with every request |
| `timeout` | `float` | `30.0` | Request timeout in seconds |

The client uses `httpx.Client` under the hood with the API key pre-configured in the default headers.

## Methods

### Pod Operations

#### `get_pods() -> list[dict]`

List all pods with current balances.

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

Total balance across all pods.

```python
total = client.get_total_balance()
# {
#   "total_balance_cents": 500000,
#   "total_balance": "$5,000.00",
#   "pod_count": 4
# }
```

#### `get_pod_balance(pod_name: str) -> dict | None`

Single pod balance by name. Returns `None` if the pod is not found (404 response).

```python
pod = client.get_pod_balance("emergency")
# {"id": "...", "name": "Emergency Fund", ...}

pod = client.get_pod_balance("nonexistent")
# None
```

#### `get_pod_detail(pod_id: str) -> dict`

Detailed pod information including recent transfers. Uses the server's default organization ID.

```python
detail = client.get_pod_detail("pod-uuid")
```

### Account Operations

#### `get_all_accounts() -> dict`

All account types: pods, ports, and external accounts.

```python
accounts = client.get_all_accounts()
# {
#   "pods": [...],
#   "ports": [...],
#   "accounts": [...]
# }
```

### Activity Operations

#### `get_activity_summary() -> dict`

Monthly activity summary.

```python
summary = client.get_activity_summary()
# {
#   "transfer_count": 12,
#   "rule_executions": 5,
#   "total_incoming_cents": 300000,
#   "total_incoming": "$3,000.00"
# }
```

#### `get_activity(first=10, statuses=None, directions=None, activity_types=None) -> dict`

Paginated transfer activity with optional filters.

```python
# Get the last 20 completed transfers
activity = client.get_activity(
    first=20,
    statuses=["COMPLETE"],
)

# Filter by direction
incoming = client.get_activity(
    directions=["INCOMING"],
)

# Filter by activity type
ach_transfers = client.get_activity(
    activity_types=["ACH"],
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `first` | `int` | `10` | Number of transfers to return |
| `statuses` | `list[str] \| None` | `None` | Filter by status: `PENDING`, `PROCESSING`, `COMPLETE`, `FAILED`, `CANCELLED` |
| `directions` | `list[str] \| None` | `None` | Filter by direction: `INTERNAL`, `INCOMING`, `OUTGOING` |
| `activity_types` | `list[str] \| None` | `None` | Filter by type: `ONE_TIME_TRANSFER`, `RULE`, `DIRECT_DEPOSIT`, `ACH` |

**Response:**

```json
{
  "transfers": [
    {
      "id": "transfer-uuid",
      "status": "COMPLETE",
      "amount_cents": 5000,
      "amount": "$50.00",
      "source": {"name": "Checking"},
      "destination": {"name": "Savings"},
      "direction": "INTERNAL",
      "activity_type": "ONE_TIME_TRANSFER",
      "created_at": "2025-01-15T10:30:00-05:00"
    }
  ],
  "page_info": {
    "end_cursor": "cursor-string",
    "has_next_page": true
  }
}
```

#### `get_transfer_detail(transfer_id: str) -> dict`

Full transfer detail with status tracking.

```python
detail = client.get_transfer_detail("transfer-uuid")
```

### Transfer Operations

#### `transfer(source_id, destination_id, amount_cents, description="") -> dict`

Execute a fund transfer. The transfer passes through the server's safeguards (per-transfer limit, daily limit, audit trail).

```python
result = client.transfer(
    source_id="source-pod-uuid",
    destination_id="dest-pod-uuid",
    amount_cents=500,            # $5.00
    description="Monthly savings",  # optional
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_id` | `str` | -- | UUID of the source pod/port/account |
| `destination_id` | `str` | -- | UUID of the destination pod/port/account |
| `amount_cents` | `int` | -- | Amount in cents (e.g. 500 = $5.00) |
| `description` | `str` | `""` | Optional ACH description |

Raises `ApiError` if the transfer fails.

### Session Management

#### `close() -> None`

Close the underlying HTTP session. Call this when you are done making requests.

```python
client.close()
```

## Error Handling

All HTTP errors (status code >= 400) raise `ApiError`:

```python
from pysequence_client import SequenceApiClient, ApiError

client = SequenceApiClient(
    base_url="http://localhost:8720",
    api_key="your-api-key",
)

try:
    result = client.transfer(
        source_id="source-uuid",
        destination_id="dest-uuid",
        amount_cents=50000000,  # exceeds limit
    )
except ApiError as e:
    print(e.status_code)  # 400
    print(e.detail)       # "Amount 50000000 cents exceeds per-transfer limit of 1000000 cents"
```

### ApiError

```python
class ApiError(Exception):
    status_code: int  # HTTP status code (e.g. 400, 401, 404, 502)
    detail: str       # Error message from the server
```

**Common error codes:**

| Status Code | Cause |
|-------------|-------|
| 400 | Transfer limit exceeded, invalid request, or upstream transfer failure |
| 401 | Invalid or missing API key |
| 404 | Resource not found (e.g. pod name lookup) |
| 502 | Upstream GraphQL/network error |

The client automatically parses JSON error responses to extract the `detail` field. For non-JSON responses, the raw response text is used as the detail.
