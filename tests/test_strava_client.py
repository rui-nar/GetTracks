"""Unit tests for StravaAPI client with mocked requests."""

import time
import pytest
from unittest.mock import patch

from src.config.settings import Config
from src.api.strava_client import StravaAPI
from src.auth.oauth import OAuth2Session
from src.auth.token_store import TokenStore
from src.exceptions.errors import APIError, AuthenticationError


class DummyConfig(Config):
    def __init__(self):
        super().__init__()
        self.set("strava.client_id", "id")
        self.set("strava.client_secret", "secret")


def test_set_token_and_store(tmp_path, monkeypatch):
    config = DummyConfig()
    client = StravaAPI(config)

    dummy_token = {"access_token": "abc", "refresh_token": "r", "expires_at": time.time() + 1000}
    client.set_token(dummy_token)
    assert client.token_data["access_token"] == "abc"


@patch("src.api.strava_client.TokenStore.save_token")
@patch("src.api.strava_client.TokenStore.load_token")
def test_ensure_token_refresh(mock_load, mock_save, monkeypatch):
    # expired token -> refresh call
    expired = {"access_token": "old", "refresh_token": "r", "expires_at": time.time() - 10}
    mock_load.return_value = expired
    config = DummyConfig()
    client = StravaAPI(config)

    refreshed = {"access_token": "new", "refresh_token": "r2", "expires_at": time.time() + 1000}
    monkeypatch.setattr(OAuth2Session, "refresh_token", lambda self, rt: refreshed)

    client._ensure_token()
    assert client.token_data["access_token"] == "new"
    mock_save.assert_called_once()


def test_request_without_token_raises():
    config = DummyConfig()
    client = StravaAPI(config)
    client.token_data = {}
    with pytest.raises(AuthenticationError):
        client.request("GET", "/athlete/activities")


@patch("src.api.strava_client.requests.request")
def test_request_api_error(mock_req):
    config = DummyConfig()
    client = StravaAPI(config)
    client.token_data = {"access_token": "t", "expires_at": time.time() + 1000}

    mock_req.return_value.status_code = 500
    mock_req.return_value.text = "oops"
    with pytest.raises(APIError):
        client.request("GET", "/athlete/activities")

@patch("src.api.strava_client.requests.request")
def test_get_activities_success(mock_req):
    config = DummyConfig()
    client = StravaAPI(config)
    client.token_data = {"access_token": "t", "expires_at": time.time() + 1000}

    mock_req.return_value.status_code = 200
    mock_req.return_value.json.return_value = [{"id": 1}]

    result = client.get_activities()
    assert result == [{"id": 1}]
