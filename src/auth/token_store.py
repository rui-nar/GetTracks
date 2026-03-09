"""Token storage utilities using keyring."""

import json
import keyring
from typing import Optional

from src.exceptions.errors import TokenError


class TokenStore:
    """Store and retrieve tokens using keyring."""

    SERVICE_NAME = "GetTracks_Strava"

    @staticmethod
    def save_token(user_id: str, token_data: dict) -> None:
        try:
            keyring.set_password(TokenStore.SERVICE_NAME, user_id, json.dumps(token_data))
        except Exception as e:
            raise TokenError(f"Unable to save token: {e}")

    @staticmethod
    def load_token(user_id: str) -> Optional[dict]:
        try:
            data = keyring.get_password(TokenStore.SERVICE_NAME, user_id)
            return json.loads(data) if data else None
        except Exception as e:
            raise TokenError(f"Unable to load token: {e}")

    @staticmethod
    def delete_token(user_id: str) -> None:
        """Delete stored token."""
        try:
            keyring.delete_password(TokenStore.SERVICE_NAME, user_id)
        except Exception as e:
            raise TokenError(f"Unable to delete token: {e}")
