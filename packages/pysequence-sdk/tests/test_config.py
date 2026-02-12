"""Unit tests for pysequence_sdk.config."""

import pytest

from pysequence_sdk.config import (
    SequenceConfig,
    SequenceCredentials,
    get_credentials,
    get_sequence_config,
)


class TestGetCredentials:
    def test_reads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SEQUENCE_EMAIL", "user@example.com")
        monkeypatch.setenv("SEQUENCE_PASSWORD", "s3cret")
        monkeypatch.setenv("SEQUENCE_TOTP", "654321")

        creds = get_credentials()

        assert isinstance(creds, SequenceCredentials)
        assert creds.email == "user@example.com"
        assert creds.password == "s3cret"
        assert creds.totp == "654321"

    def test_raises_on_missing_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SEQUENCE_EMAIL", raising=False)
        monkeypatch.delenv("SEQUENCE_PASSWORD", raising=False)
        monkeypatch.delenv("SEQUENCE_TOTP", raising=False)

        with pytest.raises(KeyError):
            get_credentials()


class TestGetSequenceConfig:
    def test_reads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SEQUENCE_ORG_ID", "org-123")
        monkeypatch.setenv("SEQUENCE_KYC_ID", "kyc-456")
        monkeypatch.setenv("SEQUENCE_AUTH0_CLIENT_ID", "client-789")

        seq = get_sequence_config()

        assert isinstance(seq, SequenceConfig)
        assert seq.organization_id == "org-123"
        assert seq.kyc_id == "kyc-456"
        assert seq.auth0_client_id == "client-789"

    def test_raises_on_missing_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SEQUENCE_ORG_ID", raising=False)
        monkeypatch.delenv("SEQUENCE_KYC_ID", raising=False)
        monkeypatch.delenv("SEQUENCE_AUTH0_CLIENT_ID", raising=False)

        with pytest.raises(KeyError):
            get_sequence_config()
