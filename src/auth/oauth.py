"""OAuth2 helper for Strava authentication."""

import webbrowser
import requests
from urllib.parse import urlencode
from typing import Any, Dict, Optional

from src.config.settings import Config
from src.exceptions.errors import AuthenticationError, TokenError, ConfigurationError


class OAuth2Session:
    """Simple OAuth2 session manager for Strava."""

    AUTH_URL = "https://www.strava.com/oauth/authorize"
    TOKEN_URL = "https://www.strava.com/oauth/token"

    def __init__(self, config: Config):
        self.config = config
        self.client_id = config.get("strava.client_id")
        self.client_secret = config.get("strava.client_secret")
        self.redirect_uri = config.get("strava.redirect_uri")
        if not self.client_id or not self.client_secret:
            raise ConfigurationError("Strava client_id/secret not configured")

    def authorization_url(self, scope: str = "activity:read_all") -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "approval_prompt": "auto",
            "scope": scope,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    def open_authorization(self, scope: str = "activity:read_all") -> None:
        url = self.authorization_url(scope)
        webbrowser.open(url)

    def exchange_code(self, code: str) -> Dict[str, Any]:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
        }
        resp = requests.post(self.TOKEN_URL, data=data)
        if resp.status_code != 200:
            raise AuthenticationError(f"Failed to exchange code: {resp.text}")
        token_data = resp.json()
        return token_data

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        try:
            resp = requests.post(self.TOKEN_URL, data=data, timeout=15)
        except requests.RequestException as exc:
            # Network-level failure — the refresh token may still be valid.
            # Raise TokenError so callers know NOT to discard it.
            raise TokenError(f"Network error during token refresh: {exc}") from exc

        if resp.status_code == 401:
            # Strava explicitly rejected the token — it is invalid or revoked.
            # Raise AuthenticationError so callers know to discard it.
            raise AuthenticationError(
                f"Refresh token rejected by Strava (401): {resp.text}"
            )
        if resp.status_code != 200:
            raise TokenError(f"Failed to refresh token ({resp.status_code}): {resp.text}")
        return resp.json()
