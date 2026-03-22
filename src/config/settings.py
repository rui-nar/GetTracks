"""Configuration management for GetTracks."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from src.exceptions.errors import ConfigurationError

_USER_SETTINGS_PATH = Path.home() / ".config" / "GetTracks" / "settings.json"


class Config:
    """Configuration management for GetTracks."""

    DEFAULT_CONFIG = {
        "strava": {
            "client_id": "",
            "client_secret": "",
            "redirect_uri": "http://localhost:8000/callback",
        },
        "app": {
            "debug": False,
            "log_level": "INFO",
            "cache_dir": "cache",
            "logs_dir": "logs",
        },
    }

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration.

        Args:
            config_file: Path to config file (uses default if not provided)

        Raises:
            ConfigurationError: If config file is invalid
        """
        if config_file:
            self.config_file = Path(config_file)
        else:
            # Try multiple common locations
            possible_paths = [
                Path("config/config.json"),  # config/ subdirectory
                Path("config.json"),           # current directory
                Path(".") / "config" / "config.json",  # relative to project
            ]
            
            self.config_file = None
            for path in possible_paths:
                if path.exists():
                    self.config_file = path
                    break
            
            # Default to config/config.json if none found
            if self.config_file is None:
                self.config_file = Path("config/config.json")
        
        self._config: Dict[str, Any] = {}
        self.load()
        self._load_user_settings()

    def load(self) -> None:
        """
        Load configuration from file or use defaults.

        Raises:
            ConfigurationError: If JSON is invalid
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    self._config = json.load(f)
            except json.JSONDecodeError as e:
                raise ConfigurationError(f"Invalid JSON in config file: {e}")
        else:
            self._config = self.DEFAULT_CONFIG.copy()
            self.save()

    def _load_user_settings(self) -> None:
        """Overlay user settings (~/.config/GetTracks/settings.json) over project config."""
        if not _USER_SETTINGS_PATH.exists():
            return
        try:
            with open(_USER_SETTINGS_PATH, "r") as f:
                user = json.load(f)
            for block in ("strava", "polarsteps", "appearance", "animation"):
                if block in user and isinstance(user[block], dict):
                    if block not in self._config:
                        self._config[block] = {}
                    self._config[block].update(user[block])
        except (json.JSONDecodeError, OSError):
            pass

    def save_user_settings(self) -> None:
        """Persist credentials and appearance settings to ~/.config/GetTracks/settings.json."""
        _USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Read existing file so we don't clobber blocks we don't own
        existing: Dict[str, Any] = {}
        if _USER_SETTINGS_PATH.exists():
            try:
                with open(_USER_SETTINGS_PATH, "r") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        existing["strava"] = {
            "client_id": self.get("strava.client_id", ""),
            "client_secret": self.get("strava.client_secret", ""),
            "redirect_uri": self.get("strava.redirect_uri", "http://localhost:8000/callback"),
        }
        existing["polarsteps"] = {
            "username": self.get("polarsteps.username", ""),
            "remember_token": self.get("polarsteps.remember_token", ""),
        }
        with open(_USER_SETTINGS_PATH, "w") as f:
            json.dump(existing, f, indent=2)

    def get_appearance(self) -> Dict[str, Any]:
        """Return appearance settings with defaults."""
        return {
            "tile_provider":    self.get("appearance.tile_provider", "OpenStreetMap"),
            "transport_radius": float(self.get("appearance.transport_radius", 10)),
            "transport_color":  self.get("appearance.transport_color", None),
            "circle_radius":    float(self.get("appearance.circle_radius", 6)),
            "circle_color":     self.get("appearance.circle_color", None),
            "waypoint_radius":  float(self.get("appearance.waypoint_radius", 10)),
            "waypoint_color":   self.get("appearance.waypoint_color", "#FF8F00"),
        }

    def save_appearance_settings(self, d: Dict[str, Any]) -> None:
        """Persist appearance settings to ~/.config/GetTracks/settings.json."""
        for k, v in d.items():
            self.set(f"appearance.{k}", v)
        _USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing: Dict[str, Any] = {}
        if _USER_SETTINGS_PATH.exists():
            try:
                with open(_USER_SETTINGS_PATH, "r") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        existing["appearance"] = dict(d)
        with open(_USER_SETTINGS_PATH, "w") as f:
            json.dump(existing, f, indent=2)

    def save(self) -> None:
        """Save current configuration to file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key: Configuration key (e.g., 'strava.client_id')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value using dot notation.

        Args:
            key: Configuration key (e.g., 'strava.client_id')
            value: Value to set
        """
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    # Default visual pacing speeds for connecting-segment animation (km/h).
    # Lower than real-world speeds so segments look comparable to GPS activities.
    _ANIM_SPEED_DEFAULTS: Dict[str, float] = {
        "flight": 250.0,
        "train":   40.0,
        "boat":    15.0,
        "bus":     35.0,
    }

    def get_animation_speeds(self) -> Dict[str, float]:
        """Return connecting-segment visual pacing speeds (km/h), with defaults."""
        stored = self.get("animation.segment_speeds", {}) or {}
        return {
            key: float(stored.get(key, default))
            for key, default in self._ANIM_SPEED_DEFAULTS.items()
        }

    def save_animation_speeds(self, speeds: Dict[str, float]) -> None:
        """Persist connecting-segment speeds to ~/.config/GetTracks/settings.json."""
        self.set("animation.segment_speeds", {k: float(v) for k, v in speeds.items()})
        _USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing: Dict[str, Any] = {}
        if _USER_SETTINGS_PATH.exists():
            try:
                with open(_USER_SETTINGS_PATH, "r") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        anim = existing.setdefault("animation", {})
        anim["segment_speeds"] = {k: float(v) for k, v in speeds.items()}
        with open(_USER_SETTINGS_PATH, "w") as f:
            json.dump(existing, f, indent=2)

    def validate_strava_config(self) -> bool:
        """
        Validate Strava configuration.

        Returns:
            True if valid Strava config exists
        """
        client_id = self.get("strava.client_id")
        client_secret = self.get("strava.client_secret")
        return bool(client_id and client_secret)

    def validate_polarsteps_config(self) -> bool:
        """Return True if both Polarsteps username and remember_token are set."""
        username = self.get("polarsteps.username")
        token = self.get("polarsteps.remember_token")
        return bool(username and token)