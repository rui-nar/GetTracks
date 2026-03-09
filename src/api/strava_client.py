"""Strava API client for GetTracks."""

import requests
import time
from typing import Dict, Optional

from src.config.settings import Config
from src.auth.oauth import OAuth2Session
from src.auth.token_store import TokenStore
from src.exceptions.errors import APIError, AuthenticationError, TokenError


class StravaAPI:
    """Client for interacting with the Strava API."""

    BASE_URL = "https://www.strava.com/api/v3"

    def __init__(self, config: Config, user_id: str = "default"):
        self.config = config
        self.user_id = user_id
        self.oauth = OAuth2Session(config)
        self.token_data = TokenStore.load_token(user_id) or {}

    def _ensure_token(self) -> None:
        """Ensure access token is valid, refresh if needed."""
        if not self.token_data:
            raise AuthenticationError("No token data available. Please authenticate with Strava.")

        # simple expiration check
        if self.token_data.get("expires_at", 0) < time.time():
            try:
                self.token_data = self.oauth.refresh_token(self.token_data.get("refresh_token"))
                TokenStore.save_token(self.user_id, self.token_data)
            except TokenError as e:
                # Token refresh failed - clear the invalid token
                self.clear_token()
                raise AuthenticationError(
                    "Token refresh failed. Please re-authenticate with Strava. "
                    f"Error: {str(e)}"
                )

    def clear_token(self) -> None:
        """Clear stored token data."""
        self.token_data = {}
        try:
            TokenStore.delete_token(self.user_id)
        except Exception:
            pass  # Token might not exist or can't be deleted

    def set_token(self, token_data: Dict[str, any]) -> None:
        """Store initial token data."""
        self.token_data = token_data
        TokenStore.save_token(self.user_id, token_data)

    def request(self, method: str, path: str, **kwargs) -> Dict[str, any]:
        """Make authenticated request to Strava API."""
        self._ensure_token()
        headers = {"Authorization": f"Bearer {self.token_data['access_token']}"}
        url = f"{self.BASE_URL}{path}"
        resp = requests.request(method, url, headers=headers, **kwargs)
        if resp.status_code >= 400:
            raise APIError(f"Strava API error {resp.status_code}: {resp.text}")
        return resp.json()

    def get_activities(self, **params) -> Dict[str, any]:
        """Fetch list of activities."""
        return self.request("GET", "/athlete/activities", params=params)

    # other API methods would follow
