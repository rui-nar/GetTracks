# GetTracks Project Structure

## Overview

This document describes the organization of the GetTracks project.

## Directory Structure

```
GetTracks/
├── .venv/                    # Python virtual environment (generated)
├── .git/                     # Git repository
├── .vscode/                  # VS Code settings
├── .pytest_cache/            # Pytest cache (generated)
│
├── assets/                   # Design and image assets
│   ├── app_icon.png
│   └── app_icon.svg
│
├── config/                   # Configuration and setup scripts
│   ├── config.json          # Application configuration
│   ├── setup.bat            # Setup script (Windows)
│   └── launch.bat           # Launch script (Windows)
│
├── docs/                     # Documentation
│   ├── architecture.md       # System architecture
│   ├── DEVELOPMENT_PLAN.md   # Development roadmap
│   └── features.md           # Feature list
│
├── scripts/                  # Utility scripts
│   ├── convert_icon.py       # Icon conversion
│   ├── release.py            # Release management
│   └── version.py            # Version management
│
├── src/                      # Application source code
│   ├── api/                  # Strava API client
│   │   └── strava_client.py
│   ├── auth/                 # Authentication
│   │   ├── oauth.py
│   │   ├── token_store.py
│   │   └── callback_handler.py
│   ├── config/               # Configuration management
│   │   └── settings.py
│   ├── exceptions/           # Custom exceptions
│   │   └── errors.py
│   ├── gui/                  # GUI components
│   │   └── main_window.py
│   ├── models/               # Data models
│   │   └── activity.py
│   ├── utils/                # Utility functions
│   │   └── logging.py
│   └── __init__.py
│
├── tests/                    # Test suite
│   ├── test_config.py
│   ├── test_exceptions.py
│   ├── test_gui.py
│   ├── test_logging.py
│   ├── test_main.py
│   ├── test_oauth.py
│   ├── test_oauth_real.py
│   ├── test_strava_client.py
│   ├── test_gui_launch.py
│   └── __init__.py
│
├── main.py                   # Application entry point
├── setup.bat                 # Setup script (Windows) - root launcher
├── launch.bat                # Launch script (Windows) - root launcher
├── README.md                 # Project readme
├── requirements.txt          # Python dependencies
└── .gitignore               # Git ignore rules
```

## File Description

### Root Level

- **main.py**: Main application entry point. Configures paths and launches the GUI.
- **setup.bat**: Windows setup script to create virtual environment and install dependencies.
- **launch.bat**: Windows launcher script to run the application.
- **requirements.txt**: Python package dependencies.
- **README.md**: Project documentation and usage guide.

### `/assets`

Design assets and icons used by the application.

### `/config`

Application configuration and setup files:
- **config.json**: Strava API credentials and app settings
- **setup.bat**: Alternative setup script location
- **launch.bat**: Alternative launcher location

### `/docs`

Documentation files:
- **architecture.md**: System design and architecture
- **DEVELOPMENT_PLAN.md**: Feature roadmap and development phases
- **features.md**: Feature overview and capabilities

### `/scripts`

Utility scripts for development and maintenance:
- **convert_icon.py**: Convert icons between formats
- **release.py**: Release management automation
- **version.py**: Version management utilities

### `/src`

Core application source code organized by module:

- **api/**: Strava API interaction
- **auth/**: OAuth2 authentication and token management
- **config/**: Configuration management
- **exceptions/**: Custom exception definitions
- **gui/**: PyQt6-based graphical user interface
- **models/**: Data models (Activity, etc.)
- **utils/**: Utility functions (logging, etc.)

### `/tests`

Test suite including:
- **Unit tests** for individual modules
- **Integration tests** (test_oauth_real.py, test_gui_launch.py)
- **GUI tests** for UI components

## Configuration

Application configuration is stored in `config/config.json` and includes:
- Strava API credentials (`client_id`, `client_secret`, `redirect_uri`)
- Application settings (debug mode, logging level, cache/logs directories)

## Getting Started

1. Run `setup.bat` to create virtual environment and install dependencies
2. Run `launch.bat` to start the application
3. Or manually: `.venv\Scripts\python.exe main.py`

## Development

- All source code is in `/src`
- Tests are in `/tests` - run with `pytest`
- Documentation in `/docs`
- Utility scripts in `/scripts`
