"""Unit tests for custom exceptions."""

import pytest

from src.exceptions.errors import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    ExportError,
    GetTracksException,
    GPXError,
    TokenError,
    ValidationError,
)


class TestExceptions:
    """Test custom exception classes."""

    def test_base_exception(self):
        """Test GetTracksException can be raised and caught."""
        with pytest.raises(GetTracksException):
            raise GetTracksException("Test error")

    def test_configuration_error(self):
        """Test ConfigurationError is a GetTracksException."""
        error = ConfigurationError("Config error")
        assert isinstance(error, GetTracksException)
        with pytest.raises(ConfigurationError):
            raise error

    def test_authentication_error(self):
        """Test AuthenticationError is a GetTracksException."""
        error = AuthenticationError("Auth failed")
        assert isinstance(error, GetTracksException)

    def test_api_error(self):
        """Test APIError is a GetTracksException."""
        error = APIError("API call failed")
        assert isinstance(error, GetTracksException)

    def test_token_error(self):
        """Test TokenError is a GetTracksException."""
        error = TokenError("Token expired")
        assert isinstance(error, GetTracksException)

    def test_validation_error(self):
        """Test ValidationError is a GetTracksException."""
        error = ValidationError("Invalid data")
        assert isinstance(error, GetTracksException)

    def test_export_error(self):
        """Test ExportError is a GetTracksException."""
        error = ExportError("Export failed")
        assert isinstance(error, GetTracksException)

    def test_gpx_error(self):
        """Test GPXError is a GetTracksException."""
        error = GPXError("GPX parse error")
        assert isinstance(error, GetTracksException)

    def test_exception_message(self):
        """Test exception message is preserved."""
        message = "Test error message"
        error = GetTracksException(message)
        assert str(error) == message