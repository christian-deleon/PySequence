# pysequence-api

FastAPI REST server wrapping the [pysequence-sdk](https://github.com/christian-deleon/PySequence/tree/main/packages/pysequence-sdk) with API-key authentication and transfer safeguards.

## Quick Start

```bash
docker compose -f compose.api.yaml up -d
# Or with justfile:
just api-up
```

## Endpoints

All routes except `/api/health` require the `X-API-Key` header.

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

## Transfer Safeguards

- **Per-transfer limit** -- Rejects transfers above $10,000 (configurable via `SEQUENCE_MAX_TRANSFER_CENTS`)
- **Global daily limit** -- Rejects when cumulative daily total exceeds $25,000 (configurable via `SEQUENCE_MAX_DAILY_TRANSFER_CENTS`)
- **Audit trail** -- Every transfer attempt logged to `.audit.jsonl`

## Requirements

- Python >= 3.11

## Documentation

[Full documentation](https://github.com/christian-deleon/PySequence/blob/main/docs/api-server.md)

## License

[MIT](https://github.com/christian-deleon/PySequence/blob/main/LICENSE)
