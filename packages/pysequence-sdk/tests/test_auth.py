"""Unit tests for pysequence_sdk.auth."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from pysequence_sdk.auth import (
    AuthTokens,
    _load_tokens,
    _save_tokens,
    authenticate,
    get_access_token,
    refresh,
)


class FakeResponse:
    """Minimal stand-in for a curl_cffi Response."""

    def __init__(self, status_code: int, _json: dict, text: str = ""):
        self.status_code = status_code
        self._json = _json
        self.text = text

    def json(self):
        return self._json


# -- _save_tokens / _load_tokens -------------------------------------------


class TestTokenPersistence:
    def test_save_and_load_roundtrip(self, tmp_token_file: Path) -> None:
        tokens = AuthTokens(
            access_token="abc",
            refresh_token="xyz",
            expires_at=1700000000.0,
        )
        _save_tokens(tokens)
        loaded = _load_tokens()
        assert loaded == tokens

    def test_load_returns_none_when_file_missing(self, tmp_token_file: Path) -> None:
        assert _load_tokens() is None

    def test_load_returns_none_on_corrupt_json(self, tmp_token_file: Path) -> None:
        tmp_token_file.write_text("not json")
        assert _load_tokens() is None

    def test_load_returns_none_on_missing_keys(self, tmp_token_file: Path) -> None:
        tmp_token_file.write_text(json.dumps({"access_token": "abc"}))
        assert _load_tokens() is None

    def test_save_overwrites_existing(self, tmp_token_file: Path) -> None:
        first = AuthTokens("a", "b", 1.0)
        second = AuthTokens("c", "d", 2.0)
        _save_tokens(first)
        _save_tokens(second)
        assert _load_tokens() == second


# -- authenticate -----------------------------------------------------------


def _make_playwright_mocks():
    """Create standard Playwright mock objects."""
    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_browser = MagicMock()
    mock_pw = MagicMock()

    mock_pw.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    mock_sp = MagicMock()
    mock_sp.__enter__ = MagicMock(return_value=mock_pw)
    mock_sp.__exit__ = MagicMock(return_value=False)

    return mock_sp, mock_browser, mock_context, mock_page


def _setup_session_storage(mock_page, access_token=None):
    """Configure mock page.evaluate to return access_token from sessionStorage."""
    if access_token:
        mock_page.evaluate.return_value = access_token
    else:
        mock_page.evaluate.return_value = None


class TestAuthenticate:
    def test_browser_login_captures_tokens(
        self, tmp_token_file: Path, fake_config: None
    ) -> None:
        """Browser login extracts access token from sessionStorage."""
        mock_sp, mock_browser, mock_context, mock_page = _make_playwright_mocks()
        _setup_session_storage(mock_page, "browser-at")

        with patch("pysequence_sdk.auth.sync_playwright", return_value=mock_sp):
            tokens = authenticate()

        assert tokens.access_token == "browser-at"
        assert tokens.refresh_token is None
        assert tokens.expires_at > time.time()
        assert _load_tokens() == tokens

    def test_no_token_captured_raises(
        self, tmp_token_file: Path, fake_config: None
    ) -> None:
        """Raises RuntimeError if no access token found in sessionStorage."""
        mock_sp, mock_browser, mock_context, mock_page = _make_playwright_mocks()
        _setup_session_storage(mock_page, access_token=None)

        with (
            patch("pysequence_sdk.auth.sync_playwright", return_value=mock_sp),
            patch("pysequence_sdk.auth.time") as mock_time,
        ):
            # Make the deadline loop exit immediately
            mock_time.time.side_effect = [100, 200]
            with pytest.raises(RuntimeError, match="no access token found"):
                authenticate()

    def test_browser_configuration_applied(
        self, tmp_token_file: Path, fake_config: None
    ) -> None:
        """Verifies navigator.webdriver patch is applied."""
        mock_sp, mock_browser, mock_context, mock_page = _make_playwright_mocks()
        _setup_session_storage(mock_page, "at")

        with patch("pysequence_sdk.auth.sync_playwright", return_value=mock_sp):
            authenticate()

        mock_context.add_init_script.assert_called_once()
        script = mock_context.add_init_script.call_args[0][0]
        assert "webdriver" in script

    def test_per_character_typing_used(
        self, tmp_token_file: Path, fake_config: None
    ) -> None:
        """Verifies that keyboard.type is called per-character."""
        mock_sp, mock_browser, mock_context, mock_page = _make_playwright_mocks()
        _setup_session_storage(mock_page, "at")

        with patch("pysequence_sdk.auth.sync_playwright", return_value=mock_sp):
            authenticate()

        # keyboard.type should be called once per character of email + password + totp
        # email="test@example.com" (16) + password="testpass" (8) + totp="123456" (6) = 30
        assert mock_page.keyboard.type.call_count == 30


# -- refresh ----------------------------------------------------------------


class TestRefresh:
    def test_success(self, tmp_token_file: Path, fake_config: None) -> None:
        resp = FakeResponse(
            status_code=200,
            _json={
                "access_token": "at-refreshed",
                "refresh_token": "rt-rotated",
                "expires_in": 86400,
            },
        )

        mock_session = MagicMock()
        mock_session.post.return_value = resp
        mock_session.__enter__ = lambda self: self
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch("pysequence_sdk.auth.Session", return_value=mock_session):
            tokens = refresh("old-rt")

        assert tokens.access_token == "at-refreshed"
        assert tokens.refresh_token == "rt-rotated"
        assert _load_tokens() == tokens

    def test_keeps_old_refresh_token_when_not_rotated(
        self, tmp_token_file: Path, fake_config: None
    ) -> None:
        resp = FakeResponse(
            status_code=200,
            _json={
                "access_token": "at-new",
                "expires_in": 86400,
            },
        )

        mock_session = MagicMock()
        mock_session.post.return_value = resp
        mock_session.__enter__ = lambda self: self
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch("pysequence_sdk.auth.Session", return_value=mock_session):
            tokens = refresh("keep-this-rt")

        assert tokens.refresh_token == "keep-this-rt"

    def test_failure_raises(self, tmp_token_file: Path, fake_config: None) -> None:
        resp = FakeResponse(
            status_code=401,
            _json={"error": "invalid_grant", "error_description": "Token revoked"},
        )

        mock_session = MagicMock()
        mock_session.post.return_value = resp
        mock_session.__enter__ = lambda self: self
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch("pysequence_sdk.auth.Session", return_value=mock_session):
            with pytest.raises(RuntimeError, match="token refresh failed"):
                refresh("bad-rt")


# -- get_access_token -------------------------------------------------------


class TestGetAccessToken:
    def test_returns_cached_token_when_valid(self, tmp_token_file: Path) -> None:
        tokens = AuthTokens("cached-at", "rt", time.time() + 3600)
        _save_tokens(tokens)
        assert get_access_token() == "cached-at"

    def test_refreshes_when_expired(
        self, tmp_token_file: Path, fake_config: None
    ) -> None:
        expired = AuthTokens("old-at", "valid-rt", time.time() - 100)
        _save_tokens(expired)

        resp = FakeResponse(
            status_code=200,
            _json={
                "access_token": "refreshed-at",
                "refresh_token": "new-rt",
                "expires_in": 86400,
            },
        )

        mock_session = MagicMock()
        mock_session.post.return_value = resp
        mock_session.__enter__ = lambda self: self
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch("pysequence_sdk.auth.Session", return_value=mock_session):
            token = get_access_token()

        assert token == "refreshed-at"

    def test_full_auth_when_no_cache(
        self, tmp_token_file: Path, fake_config: None
    ) -> None:
        # No tokens file exists — should call authenticate()
        with patch("pysequence_sdk.auth.authenticate") as mock_auth:
            mock_auth.return_value = AuthTokens(
                "brand-new-at", "brand-new-rt", time.time() + 86400
            )
            token = get_access_token()

        assert token == "brand-new-at"

    def test_falls_back_to_auth_when_refresh_fails(
        self, tmp_token_file: Path, fake_config: None
    ) -> None:
        expired = AuthTokens("old-at", "bad-rt", time.time() - 100)
        _save_tokens(expired)

        refresh_fail = FakeResponse(
            status_code=401,
            _json={"error": "invalid_grant", "error_description": "Revoked"},
        )

        mock_session = MagicMock()
        mock_session.post.return_value = refresh_fail
        mock_session.__enter__ = lambda self: self
        mock_session.__exit__ = MagicMock(return_value=False)

        with (
            patch("pysequence_sdk.auth.Session", return_value=mock_session),
            patch("pysequence_sdk.auth.authenticate") as mock_auth,
        ):
            mock_auth.return_value = AuthTokens(
                "fallback-at", "fallback-rt", time.time() + 86400
            )
            token = get_access_token()

        assert token == "fallback-at"

    def test_expired_no_refresh_token_does_full_auth(
        self, tmp_token_file: Path, fake_config: None
    ) -> None:
        expired = AuthTokens("old-at", None, time.time() - 100)
        _save_tokens(expired)

        with patch("pysequence_sdk.auth.authenticate") as mock_auth:
            mock_auth.return_value = AuthTokens("new-at", "new-rt", time.time() + 86400)
            token = get_access_token()

        assert token == "new-at"

    def test_token_within_60s_buffer_triggers_refresh(
        self, tmp_token_file: Path, fake_config: None
    ) -> None:
        """Token expires in 30s — within the 60s buffer, so should refresh."""
        almost_expired = AuthTokens("old-at", "rt", time.time() + 30)
        _save_tokens(almost_expired)

        resp = FakeResponse(
            status_code=200,
            _json={
                "access_token": "refreshed-at",
                "refresh_token": "new-rt",
                "expires_in": 86400,
            },
        )

        mock_session = MagicMock()
        mock_session.post.return_value = resp
        mock_session.__enter__ = lambda self: self
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch("pysequence_sdk.auth.Session", return_value=mock_session):
            token = get_access_token()

        assert token == "refreshed-at"
