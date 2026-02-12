"""Shared fixtures for the SDK test suite."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@dataclass
class FakeResponse:
    """Minimal stand-in for a curl_cffi Response."""

    status_code: int
    _json: dict[str, Any]
    text: str = ""

    def json(self) -> dict[str, Any]:
        return self._json


@pytest.fixture
def tmp_token_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect TOKEN_PATH to a temp file so tests don't touch the real one."""
    token_path = tmp_path / ".tokens.json"
    monkeypatch.setattr("pysequence_sdk.auth.TOKEN_PATH", token_path)
    return token_path


@pytest.fixture
def fake_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch config loaders so tests don't need env vars."""
    from pysequence_sdk.config import SequenceConfig, SequenceCredentials

    monkeypatch.setattr(
        "pysequence_sdk.auth.get_credentials",
        lambda: SequenceCredentials(
            email="test@example.com",
            password="testpass",
            totp="123456",
        ),
    )
    monkeypatch.setattr(
        "pysequence_sdk.auth.get_sequence_config",
        lambda: SequenceConfig(
            organization_id="org-1",
            kyc_id="kyc-1",
            auth0_client_id="client-id-1",
        ),
    )
