# GetTracks

A desktop GUI application for selecting and merging Strava activities into navigable GPS tracks.

## Purpose

GetTracks allows users to connect to their Strava account, select a subset of activities based on various filters, visualize them on an interactive map, and export a merged GPX track file suitable for GPS navigation.

## Features

See [features.md](features.md) for detailed feature list.

## Architecture

See [architecture.md](architecture.md) for technical decisions and design.

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run

```bash
python main.py
```

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
