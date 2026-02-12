# PySequence

[![PyPI](https://img.shields.io/pypi/v/pysequence-sdk)](https://pypi.org/project/pysequence-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/pysequence-sdk)](https://pypi.org/project/pysequence-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Unofficial Python SDK for the [GetSequence](https://getsequence.io/) personal finance platform.

## Overview

PySequence is a **toolkit, not a monolith**. Pick what you need:

- **SDK only** -- Import `pysequence-sdk` into your own Python project and talk to the Sequence GraphQL API directly. No server, no bot, no Docker.
- **API server** -- A REST trust boundary for external services. Sits in front of the SDK with API-key auth and transfer safeguards.
- **Telegram bot** -- AI-powered personal finance assistant using Claude. Uses the SDK directly with its own safeguards (daily limits, audit trail, transfer confirmation).

Each component is independently deployable.

## Packages

| Package | Description | PyPI |
|---------|-------------|------|
| [`pysequence-sdk`](packages/pysequence-sdk/) | Core GraphQL SDK | [![PyPI](https://img.shields.io/pypi/v/pysequence-sdk)](https://pypi.org/project/pysequence-sdk/) |
| [`pysequence-api`](packages/pysequence-api/) | FastAPI REST server | [![PyPI](https://img.shields.io/pypi/v/pysequence-api)](https://pypi.org/project/pysequence-api/) |
| [`pysequence-client`](packages/pysequence-client/) | HTTP client for the REST API | [![PyPI](https://img.shields.io/pypi/v/pysequence-client)](https://pypi.org/project/pysequence-client/) |
| [`pysequence-bot`](packages/pysequence-bot/) | Telegram bot with AI agent | [![PyPI](https://img.shields.io/pypi/v/pysequence-bot)](https://pypi.org/project/pysequence-bot/) |

## Architecture

```
pysequence-client --> (HTTP) --> pysequence-api --> pysequence-sdk --> (GraphQL) --> Sequence.io
                                                        ^
                                  pysequence-bot -------/
```

## Quick Start

### SDK

```bash
pip install pysequence-sdk
```

```python
from pysequence_sdk import SequenceClient, get_access_token

token = get_access_token()
with SequenceClient(token) as client:
    pods = client.get_pods()
    balance = client.get_total_balance()
```

### API Server

```bash
just api-up
```

### Telegram Bot

```bash
just bot-up
```

### HTTP Client

```bash
pip install pysequence-client
```

```python
from pysequence_client import SequenceApiClient

client = SequenceApiClient(
    base_url="http://localhost:8720",
    api_key="your-api-key",
)

pods = client.get_pods()
balance = client.get_total_balance()
```

## Documentation

- [SDK Reference](docs/sdk.md)
- [API Server](docs/api-server.md)
- [HTTP Client](docs/http-client.md)
- [Telegram Bot](docs/telegram-bot.md)
- [Configuration](docs/configuration.md)
- [Docker](docs/docker.md)
- [Development](docs/development.md)

## License

[MIT](LICENSE)
