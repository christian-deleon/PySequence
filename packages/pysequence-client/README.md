# pysequence-client

Python HTTP client for the [pysequence-api](https://github.com/christian-deleon/PySequence/tree/main/packages/pysequence-api) REST server. Standalone -- no SDK dependency.

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

pods = client.get_pods()
balance = client.get_total_balance()
```

## Methods

| Method | Description |
|--------|-------------|
| `get_pods()` | List all pods with balances |
| `get_total_balance()` | Total balance across all pods |
| `get_pod_balance(pod_name)` | Single pod balance by name |
| `get_pod_detail(pod_id)` | Detailed pod info |
| `get_all_accounts()` | All accounts: pods, ports, and external |
| `get_activity_summary()` | Monthly activity summary |
| `get_activity(first, statuses, directions, activity_types)` | Paginated transfer activity with filters |
| `get_transfer_detail(transfer_id)` | Full detail for a single transfer |
| `transfer(source_id, destination_id, amount_cents, description)` | Transfer funds between accounts |

## Error Handling

```python
from pysequence_client import SequenceApiClient
from pysequence_client.exceptions import ApiError

client = SequenceApiClient(
    base_url="http://localhost:8720",
    api_key="your-api-key",
)

try:
    detail = client.get_transfer_detail("invalid-id")
except ApiError as e:
    print(f"Status {e.status_code}: {e.detail}")
```

## Requirements

- Python >= 3.11

## Documentation

[Full documentation](https://github.com/christian-deleon/PySequence/blob/main/docs/http-client.md)

## License

[MIT](https://github.com/christian-deleon/PySequence/blob/main/LICENSE)
