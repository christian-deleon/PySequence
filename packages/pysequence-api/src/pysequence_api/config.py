import os
from dataclasses import dataclass


@dataclass
class ServerConfig:
    api_key: str
    org_id: str = ""
    kyc_id: str = ""
    host: str = "0.0.0.0"
    port: int = 8720
    max_transfer_cents: int = 1_000_000
    max_daily_transfer_cents: int = 2_500_000


def get_server_config() -> ServerConfig:
    """Get API server configuration from environment variables.

    Expected env vars: SEQUENCE_API_KEY (required),
    SEQUENCE_ORG_ID, SEQUENCE_KYC_ID (recommended for default resolution),
    SEQUENCE_SERVER_HOST, SEQUENCE_SERVER_PORT,
    SEQUENCE_MAX_TRANSFER_CENTS, SEQUENCE_MAX_DAILY_TRANSFER_CENTS (optional)
    """
    
    return ServerConfig(
        api_key=os.environ["SEQUENCE_API_KEY"],
        org_id=os.environ.get("SEQUENCE_ORG_ID", ""),
        kyc_id=os.environ.get("SEQUENCE_KYC_ID", ""),
        host=os.environ.get("SEQUENCE_SERVER_HOST", "0.0.0.0"),
        port=int(os.environ.get("SEQUENCE_SERVER_PORT", "8720")),
        max_transfer_cents=int(
            os.environ.get("SEQUENCE_MAX_TRANSFER_CENTS", "1000000")
        ),
        max_daily_transfer_cents=int(
            os.environ.get("SEQUENCE_MAX_DAILY_TRANSFER_CENTS", "2500000")
        ),
    )
