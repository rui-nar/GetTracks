# Architecture Overview

## Current Status

**Phase**: 5 (Filtering & Selection) ✅ Complete
**Next Phase**: 6/7 (GPS Track Visualization & GPX Processing)

## Technology Stack

- **Language**: Python 3.9+
- **GUI Framework**: PyQt6 + PyQt6-WebEngine
- **HTTP Client**: requests (for Strava API)
- **Authentication**: OAuth 2.0 with custom callback handler
- **Token Storage**: keyring (secure credentials storage)
- **Map Rendering**: Folium (HTML/Leaflet, embedded in QWebEngineView)
- **Data Models**: dataclasses (Python 3.7+)
- **Logging**: Python standard logging
- **Testing**: pytest + unittest.mock

## Project Structure

```
src/
├── api/              # Strava API client (rate limiting, retry)
├── auth/             # OAuth and token management
├── config/           # Configuration management
├── exceptions/       # Custom exceptions
├── filters/          # FilterEngine + FilterCriteria
├── gui/              # PyQt6 UI components
│   ├── main_window.py
│   └── filter_widget.py
├── models/           # Data classes (Activity)
├── utils/            # Utilities (logging)
└── visualization/    # Map widget (Folium + QWebEngineView)

config/              # Configuration files
docs/                # Documentation
scripts/             # Utility scripts
tests/               # Test suite
assets/              # Application icon and design assets
```

## Application Architecture

### 1. **Authentication Layer** (✅ Implemented)

**Components:**
- `src/auth/oauth.py` - OAuth2Session for Strava OAuth flow
- `src/auth/callback_handler.py` - Local HTTP server for OAuth callbacks
  (per-instance state via factory method — thread-safe, no class-level shared state)
- `src/auth/token_store.py` - Secure token storage using keyring

**Flow:**
1. User clicks "Authenticate with Strava"
2. App starts local callback server on port 8000
3. Browser opens Strava OAuth authorization page
4. User grants permissions
5. Callback handler receives authorization code
6. Code exchanged for access token via `urlencode`-safe URL
7. Token stored securely in system keyring

### 2. **API Client Layer** (✅ Implemented)

**Components:**
- `src/api/strava_client.py` - StravaAPI class + RateLimiter class

**RateLimiter:**
- Sliding-window counter: max 100 requests per 15-minute window
- `collections.deque` of `time.monotonic()` timestamps
- Thread-safe via `threading.Lock` (held during sleep to prevent double-booking)
- `current_usage` property for observability

**Retry Logic in `request()`:**
- HTTP 429: wait `max(Retry-After, 60)` seconds, retry
- HTTP 5xx: exponential backoff (1s, 2s, 4s), up to `max_retries` attempts
- HTTP 4xx (not 429): raise `APIError` immediately, no retry
- Exhausted retries: raise `APIError` with attempt count

**Implemented Methods:**
- `get_activities(**params)` - Fetch user's activities

**Pending Methods:**
- `get_activity_details(activity_id)` - Full activity data
- `get_activity_streams(activity_id)` - GPS coordinates and metrics

### 3. **Data Model Layer** (✅ Partial)

**Models Created:**
- `Activity` - Strava activity with full metadata
  - Basic info: id (Optional[int]), name, type
  - Distance and time metrics
  - Heart rate data
  - Engagement metrics
  - Timestamps and timezone
  - Optional GPS: start_latlng, end_latlng
  - Factory: `from_strava_api(data: dict)`

**Pending Models:**
- `Track` - GPX track with GPS route points
- `Project` - Session for merge operations

### 4. **Filter Layer** (✅ Implemented)

**Components:**
- `src/filters/filter_engine.py` - `FilterCriteria` dataclass + `FilterEngine` class

**FilterCriteria:**
- `start_date: Optional[datetime]` — None = no lower bound
- `end_date: Optional[datetime]` — None = no upper bound
- `activity_types: Optional[Set[str]]` — None = all types; empty set = nothing passes
- `is_empty()` — True when no constraints active

**FilterEngine:**
- `apply(activities, criteria)` — stateless, returns new filtered list
  - Strips tzinfo from `start_date_local` before comparison (safe with tz-naive QDate inputs)
  - Case-insensitive type matching
- `extract_activity_types(activities)` — sorted unique types for UI population

### 5. **GUI Layer** (✅ Implemented)

**Modules:**
- `src/gui/main_window.py` - Primary window + worker threads
- `src/gui/filter_widget.py` - Compact horizontal filter bar

**Layout:**
```
┌─────────────────────┬────────────────────────────────┐
│ [Auth] [Fetch]      │  Activity Details               │
│ [Sel All] [Clear]   │                                 │
│ ┌─ Filters ───────┐ ├────────────────────────────────┤
│ │ Date | Types    │ │  Map (hidden until activities   │
│ │ [Apply][Clear]  │ │  are loaded or selected)        │
│ └─────────────────┘ │                                 │
│ Activity List        │                                │
└─────────────────────┴────────────────────────────────┘
```

**Components:**
- `MainWindow` - Application window (1200×800 min)
- `ActivityListWidget` - Activity list with click-to-select
- `ActivityDetailsWidget` - Full metadata panel
- `FilterWidget` - Date range + type checkboxes + Apply/Clear
- `OAuthAuthenticationWorker` - OAuth flow in QThread
- `FetchActivitiesWorker` - Activity fetch in QThread

**State management:**
- `_all_activities` — master list from last fetch; never mutated by filters
- `_filter_engine` — stateless FilterEngine instance
- Filter signal → `_on_filters_changed` → re-apply + update list + map

**Map widget behaviour:**
- Hidden at startup (no white-box flash)
- Shown when activities are fetched (all-activities overview)
- Shown when a single activity is selected (focused view)
- Hidden when filter produces zero results
- Temp HTML file managed via Qt `destroyed` signal (not `__del__`)

### 6. **Map Visualization Layer** (✅ Partial)

**Components:**
- `src/visualization/map_widget.py` - Folium map in QWebEngineView

**Current capability:**
- Start/end point markers per activity
- Activity type color coding
- CartoDB positron / dark_matter tile layers
- Null-safe: activities without GPS are silently skipped

**Pending:**
- GPS polyline tracks (requires `get_activity_streams()`)
- Elevation profile overlay

### 7. **Configuration Layer** (✅ Implemented)

**File**: `config/config.json`

```json
{
  "strava": {
    "client_id": "...",
    "client_secret": "...",
    "redirect_uri": "http://localhost:8000/callback"
  },
  "app": {
    "debug": false,
    "log_level": "INFO",
    "cache_dir": "cache",
    "logs_dir": "logs"
  }
}
```

- `src/config/settings.py` — dot-notation access, auto-discovers config file
- Validates Strava credentials before launching GUI

### 8. **Error Handling** (✅ Implemented)

**Custom Exceptions** (`src/exceptions/errors.py`):
- `GetTracksException` — base
- `ConfigurationError`, `AuthenticationError`, `TokenError`
- `APIError`, `ValidationError`, `ExportError`, `GPXError`

### 9. **Logging & Utilities** (✅ Implemented)

- `src/utils/logging.py` — file + console logging, per-module loggers

## Data Flow

### Activity Fetch + Filter Flow
```
User clicks "Fetch Activities"
  └─> FetchActivitiesWorker (QThread)
       └─> StravaAPI._ensure_token()
       └─> RateLimiter.acquire()  ← NEW
       └─> requests.request() with retry  ← NEW
       └─> Activity.from_strava_api() for each
       └─> MainWindow.on_activities_fetched()
            └─> _all_activities = activities
            └─> FilterWidget.populate_types()
            └─> ActivityListWidget.set_activities(all)
            └─> MapWidget.display_activities(all)

User clicks "Apply" in FilterWidget
  └─> FilterWidget.build_criteria()  ← NEW
       └─> FilterCriteria(start_date, end_date, types)
  └─> MainWindow._on_filters_changed(criteria)  ← NEW
       └─> FilterEngine.apply(_all_activities, criteria)
       └─> ActivityListWidget.set_activities(filtered)
       └─> MapWidget.display_activities(filtered)
```

## Security Model

- OAuth tokens in system keyring (encrypted at OS level)
- Automatic token refresh; invalid tokens deleted
- HTTPS enforced by Strava
- OAuth redirect URL built with `urlencode` (no injection risk)
- No secrets in logs

## Testing Architecture

```
tests/
├── test_config.py           # Configuration loading
├── test_exceptions.py       # Exception hierarchy
├── test_logging.py          # Logging setup
├── test_main.py             # Entry point
├── test_oauth.py            # OAuth flow (mocked)
├── test_strava_client.py    # API client: token, retry, rate-limit (mocked)
├── test_filter_engine.py    # FilterCriteria + FilterEngine (comprehensive)
├── test_gui.py              # GUI component logic
├── test_gui_launch.py       # Full GUI smoke test
└── test_oauth_real.py       # Real Strava auth (manual)
```

## Performance Considerations

**Current:**
- Activity list fetches up to 50 items per request
- QThread workers prevent UI freezes
- Rate limiter prevents Strava 429s proactively
- Retry loop handles transient failures transparently
- Filter applied in-memory (no re-fetch needed)

**Planned:**
- Pagination for >50 activities
- Local JSON caching of activity data
- Lazy loading of GPS stream data
- Background sync

## Extensibility Points

1. **New Filter Dimensions** — add fields to `FilterCriteria`, logic to `FilterEngine.apply()`
2. **Export Formats** — add to a future `src/export/` module
3. **Map Backends** — swap Folium for another renderer in `MapWidget`
4. **Additional APIs** — duplicate `src/auth/` + `src/api/` pattern
5. **GPX Processing** — new `src/gpx/` module (Phase 7)

## Known Limitations

1. Activity list limited to 50 items (no pagination yet)
2. Map shows start/end markers only (no GPS polylines until stream API integrated)
3. No activity caching (every fetch hits Strava API)
4. No Track or Project models yet
5. No GPX export
