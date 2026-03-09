"""Custom exceptions for GetTracks application."""


class GetTracksException(Exception):
    """Base exception for GetTracks."""

    pass


class ConfigurationError(GetTracksException):
    """Raised when configuration is invalid or missing."""

    pass


class AuthenticationError(GetTracksException):
    """Raised when authentication fails."""

    pass


class APIError(GetTracksException):
    """Raised when Strava API returns an error."""

    pass


class TokenError(GetTracksException):
    """Raised when token management fails."""

    pass


class ValidationError(GetTracksException):
    """Raised when data validation fails."""

    pass


class ExportError(GetTracksException):
    """Raised when export operation fails."""

    pass


class GPXError(GetTracksException):
    """Raised when GPX processing fails."""

    pass