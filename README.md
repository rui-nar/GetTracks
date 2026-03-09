# GetTracks

A desktop GUI application for selecting and merging Strava activities into navigable GPS tracks.

## Purpose

GetTracks allows users to connect to their Strava account, select a subset of activities based on various filters, visualize them on an interactive map, and export a merged GPX track file suitable for GPS navigation.

## Features

See [features.md](features.md) for detailed feature list.

## Architecture

See [architecture.md](architecture.md) for technical decisions and design.

## Setup

### Quick Setup (Windows)
1. Double-click `setup.bat` to create the virtual environment and install dependencies
2. Configure your Strava credentials in `config.json`
3. Double-click `launch.bat` to start the application

### Manual Setup
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run

### Quick Launch (Windows)
Double-click `launch.bat` to automatically set up the environment and start the application.

### Manual Launch
To run the GUI application manually:

```bash
PYTHONPATH=src python main.py
```

Or on Windows:

```cmd
set PYTHONPATH=src
python main.py
```

This launches the PyQt6 desktop application for browsing and selecting Strava activities.

## Testing

Run unit tests with pytest:

```bash
pytest
```

All functions must have associated unit tests. No version can be released if unit tests fail.

## Release

Before releasing a new version, run the release script to ensure all tests pass:

```bash
python release.py
```

## Development

- Requires Strava API application credentials
- Built with Python and PyQt
- Uses Strava API v3 for activity data
