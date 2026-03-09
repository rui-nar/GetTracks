"""Unit tests for OAuth2Session."""

import pytest
import requests
from unittest.mock import patch

from src.config.settings import Config
from src.auth.oauth import OAuth2Session
from src.exceptions.errors import AuthenticationError, TokenError


class DummyConfig(Config):
    def __init__(self):
        super().__init__()
        self.set("strava.client_id", "id")
        self.set("strava.client_secret", "secret")


def test_authorization_url_contains_required_params():
    config = DummyConfig()
    oauth = OAuth2Session(config)
    url = oauth.authorization_url(scope="read")
    assert "client_id=id" in url
    assert "response_type=code" in url
    assert "scope=read" in url


@patch("src.auth.oauth.requests.post")
def test_exchange_code_success(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"access_token": "abc"}

    config = DummyConfig()
    oauth = OAuth2Session(config)
    result = oauth.exchange_code("code123")
    assert result["access_token"] == "abc"
    mock_post.assert_called_once()


@patch("src.auth.oauth.requests.post")
def test_exchange_code_failure(mock_post):
    mock_post.return_value.status_code = 400
    mock_post.return_value.text = "error"

    config = DummyConfig()
    oauth = OAuth2Session(config)
    with pytest.raises(AuthenticationError):
        oauth.exchange_code("badcode")


@patch("src.auth.oauth.requests.post")
def test_refresh_token_success(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"access_token": "new"}

    config = DummyConfig()
    oauth = OAuth2Session(config)
    result = oauth.refresh_token("r123")
    assert result["access_token"] == "new"


@patch("src.auth.oauth.requests.post")
def test_refresh_token_failure(mock_post):
    mock_post.return_value.status_code = 401
    mock_post.return_value.text = "fail"

    config = DummyConfig()
    oauth = OAuth2Session(config)
    with pytest.raises(TokenError):
        oauth.refresh_token("bad")