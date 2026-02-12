"""Auth0 token management for GetSequence API.

Handles authentication via headless Chromium browser login:
1. Navigate to app.getsequence.io -> Auth0 login redirect
2. Fill email + password + TOTP with per-character delays
3. Capture tokens from the Auth0 token exchange response

Tokens are cached to .tokens.json so they survive restarts.
"""

import json
import logging
import random
import time
from dataclasses import asdict, dataclass

from curl_cffi.requests import Session
from playwright.sync_api import Page, sync_playwright
from pysequence_sdk.config import DATA_DIR, get_credentials, get_sequence_config


log = logging.getLogger(__name__)

AUTH0_DOMAIN = "https://auth.getsequence.io"
SEQUENCE_APP_URL = "https://app.getsequence.io"
TOKEN_PATH = DATA_DIR / ".tokens.json"


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: float


def _save_tokens(tokens: AuthTokens) -> None:
    TOKEN_PATH.write_text(json.dumps(asdict(tokens)))
    log.debug("Tokens saved to %s", TOKEN_PATH)


def _load_tokens() -> AuthTokens | None:
    if not TOKEN_PATH.exists():
        log.debug("No token cache at %s", TOKEN_PATH)
        return None
    
    try:
        data = json.loads(TOKEN_PATH.read_text())
        return AuthTokens(**data)
    
    except (json.JSONDecodeError, KeyError, TypeError):
        log.warning("Corrupt token cache at %s, ignoring", TOKEN_PATH)
        return None


def _human_type(page: Page, selector: str, text: str) -> None:
    """Type text into a field with random per-character delays."""

    page.click(selector)

    for char in text:
        page.keyboard.type(char)
        page.wait_for_timeout(random.randint(50, 150))


def authenticate() -> AuthTokens:
    """Full Auth0 login via headless Chromium browser.

    Launches a headless browser, navigates to the app login page, clicks
    through Auth0's Universal Login (email -> password -> MFA), then
    extracts the access token from sessionStorage after the app loads.

    The app uses Auth0's implicit flow (response_type=token), so the
    token arrives as a URL fragment and the app stores it in sessionStorage.
    """

    log.info("Starting browser authentication")
    creds = get_credentials()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => false})"
        )

        page = context.new_page()

        # Navigate to app login page
        log.info("Navigating to %s", SEQUENCE_APP_URL)
        page.goto(SEQUENCE_APP_URL)
        log.info("Page loaded: %s", page.url)

        # Click "Log in" button to trigger Auth0 redirect
        page.wait_for_selector('button:has-text("Log in")')
        page.wait_for_timeout(random.randint(500, 2000))
        page.click('button:has-text("Log in")')
        log.info("Clicked 'Log in', waiting for Auth0 redirect")

        # Email field (on Auth0 login page)
        page.wait_for_selector('input[name="username"], input[type="email"]')
        log.info("Auth0 login page loaded: %s", page.url)
        page.wait_for_timeout(random.randint(500, 2000))
        _human_type(page, 'input[name="username"], input[type="email"]', creds.email)

        # Submit email
        page.wait_for_timeout(random.randint(300, 1000))
        page.click('button[type="submit"]')
        log.info("Email submitted, waiting for password field")

        # Password field (appears after email submit)
        page.wait_for_selector('input[name="password"]')
        page.wait_for_timeout(random.randint(500, 2000))
        _human_type(page, 'input[name="password"]', creds.password)

        # Submit password
        page.wait_for_timeout(random.randint(300, 1000))
        page.click('button[type="submit"]')
        log.info("Password submitted, waiting for MFA page")

        # MFA page — wait for OTP input
        page.wait_for_selector('input[name="code"], input[inputmode="numeric"]')
        log.info("MFA page loaded")
        page.wait_for_timeout(random.randint(500, 2000))
        _human_type(page, 'input[name="code"], input[inputmode="numeric"]', creds.totp)

        # Submit MFA
        page.wait_for_timeout(random.randint(300, 1000))
        page.click('button[type="submit"]')
        log.info("MFA submitted, waiting for app to load")

        # Wait for redirect back to the app and token to appear in sessionStorage
        page.wait_for_url(f"{SEQUENCE_APP_URL}/**", timeout=30000)
        log.info("Redirected to app: %s", page.url)

        # The app stores the access token in sessionStorage after processing
        # the Auth0 implicit flow callback (token arrives via URL fragment)
        access_token = None
        deadline = time.time() + 10

        while time.time() < deadline:
            access_token = page.evaluate("() => sessionStorage.getItem('access_token')")
            if access_token:
                break
            page.wait_for_timeout(500)

        if not access_token:
            log.error("No access_token in sessionStorage. Final URL: %s", page.url)
            browser.close()
            raise RuntimeError(
                "Browser login failed: no access token found in sessionStorage"
            )

        log.info("Access token extracted from sessionStorage")
        browser.close()

    tokens = AuthTokens(
        access_token=access_token,
        refresh_token=None,
        expires_at=time.time() + 86400,
    )

    _save_tokens(tokens)

    log.info(
        "Authentication successful, token expires at %s", time.ctime(tokens.expires_at)
    )

    return tokens


def refresh(refresh_token: str) -> AuthTokens:
    """Silently refresh the access token using a refresh token."""

    log.info("Refreshing access token")
    seq_config = get_sequence_config()

    with Session(impersonate="chrome", timeout=30) as s:
        resp = s.post(
            f"{AUTH0_DOMAIN}/oauth/token",
            json={
                "grant_type": "refresh_token",
                "client_id": seq_config.auth0_client_id,
                "refresh_token": refresh_token,
            },
        )

        body = resp.json()

        if resp.status_code >= 400:
            log.error(
                "Token refresh failed (HTTP %d): %s",
                resp.status_code,
                body.get("error_description", body),
            )

            raise RuntimeError(
                f"Auth0 token refresh failed (HTTP {resp.status_code}): "
                f"{body.get('error_description', body)}"
            )

        tokens = AuthTokens(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token", refresh_token),
            expires_at=time.time() + body.get("expires_in", 86400),
        )

        _save_tokens(tokens)

        log.info("Token refreshed, expires at %s", time.ctime(tokens.expires_at))

        return tokens


def get_access_token() -> str:
    """Get a valid access token, refreshing or re-authenticating as needed.

    This is the main entry point for consumers. It:
    1. Loads cached tokens from .tokens.json
    2. Returns the access token if still valid
    3. Refreshes via refresh_token if expired
    4. Falls back to full re-authentication if no refresh token
    """

    tokens = _load_tokens()

    if tokens is not None:
        remaining = tokens.expires_at - time.time()
        log.debug("Cached token found, expires in %.0fs", remaining)

        # Still valid (with 60s buffer)
        if remaining > 60:
            log.info("Using cached token (expires in %.0fs)", remaining)
            return tokens.access_token

        # Expired but we have a refresh token
        if tokens.refresh_token:
            try:
                tokens = refresh(tokens.refresh_token)
                return tokens.access_token
            except RuntimeError:
                log.warning("Refresh failed, falling back to full authentication")

    # No tokens or refresh failed — full authentication
    tokens = authenticate()
    
    return tokens.access_token
