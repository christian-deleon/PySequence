# pysequence-sdk

Unofficial Python SDK for the [GetSequence](https://getsequence.io/) personal finance platform. Communicates with the Sequence GraphQL API using browser-compatible HTTP requests.

## Installation

```bash
pip install pysequence-sdk
```

## Quick Start

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

## Methods

| Method | Description |
|--------|-------------|
| `get_pods()` | List all pods with current balances |
| `get_total_balance()` | Total balance across all pods |
| `get_pod_balance(pod_name)` | Look up a single pod by name |
| `get_pod_detail(org_id, pod_id)` | Detailed pod info with recent transfers |
| `get_all_accounts(org_id)` | All accounts: pods, ports, and external |
| `get_activity_summary()` | Monthly activity summary |
| `get_activity(org_id, ...)` | Paginated transfer activity with filters |
| `get_transfer_detail(org_id, transfer_id)` | Full detail for a single transfer |
| `transfer(kyc_id, source_id, dest_id, amount_cents, ...)` | Transfer funds between accounts |
| `execute(query, variables, operation_name)` | Execute a raw GraphQL query |

## Key Features

- **Automatic Auth0 token management** -- Handles login, refresh, and caching via `get_access_token()`
- **Browser-compatible TLS** -- Uses `curl_cffi` with Chrome impersonation for proper TLS fingerprinting
- **Built-in rate limiting** -- Automatic delay with jitter between requests
- **Pydantic models** -- Typed response models for pods, transfers, and more

## Requirements

- Python >= 3.11

## Documentation

[Full documentation](https://github.com/christian-deleon/PySequence/blob/main/docs/sdk.md)

## License

[MIT](https://github.com/christian-deleon/PySequence/blob/main/LICENSE)
