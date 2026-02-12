"""Configuration from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path


DATA_DIR = Path(os.environ.get("SEQUENCE_DATA_DIR", "."))


@dataclass
class SequenceCredentials:
    email: str
    password: str
    totp: str


@dataclass
class SequenceConfig:
    organization_id: str
    kyc_id: str
    auth0_client_id: str


def get_credentials() -> SequenceCredentials:
    """Get Sequence login credentials from environment variables.

    Expected env vars: SEQUENCE_EMAIL, SEQUENCE_PASSWORD, SEQUENCE_TOTP
    """

    return SequenceCredentials(
        email=os.environ["SEQUENCE_EMAIL"],
        password=os.environ["SEQUENCE_PASSWORD"],
        totp=os.environ["SEQUENCE_TOTP"],
    )


def get_sequence_config() -> SequenceConfig:
    """Get Sequence API configuration from environment variables.

    Expected env vars: SEQUENCE_ORG_ID, SEQUENCE_KYC_ID, SEQUENCE_AUTH0_CLIENT_ID
    """
    
    return SequenceConfig(
        organization_id=os.environ["SEQUENCE_ORG_ID"],
        kyc_id=os.environ["SEQUENCE_KYC_ID"],
        auth0_client_id=os.environ["SEQUENCE_AUTH0_CLIENT_ID"],
    )
