# Architecture Overview

## Current Status

**Phase**: 2 (Authentication & Core GUI) ✅ Complete  
**Next Phase**: 3 (Track Processing & Export)

## Technology Stack

- **Language**: Python 3.9+
- **GUI Framework**: PyQt6
- **HTTP Client**: requests (for Strava API)
- **Authentication**: OAuth 2.0 with custom callback handler
- **Token Storage**: keyring (secure credentials storage)
- **Data Models**: dataclasses (Python 3.7+)
- **Logging**: Python standard logging
- **Testing**: pytest + unittest.mock

## Project Structure

```
src/
├── api/              # Strava API client
├── auth/             # OAuth and token management
├── config/           # Configuration management
├── exceptions/       # Custom exceptions
├── gui/              # PyQt6 UI components
├── models/           # Data classes
└── utils/            # Utilities (logging, etc.)

config/              # Configuration files
docs/                # Documentation
scripts/             # Utility scripts
tests/               # Test suite
assets/              # Design assets
```

## Application Architecture

### 1. **Authentication Layer** (✅ Implemented)

**Components:**
- `src/auth/oauth.py` - OAuth2Session for Strava OAuth flow
- `src/auth/callback_handler.py` - Local HTTP server for OAuth callbacks
- `src/auth/token_store.py` - Secure token storage using keyring

**Flow:**
1. User clicks "Authenticate with Strava" button
2. App starts local callback server on port 8000
3. Browser opens Strava OAuth authorization page
4. User grants permissions
5. Callback handler receives authorization code
6. Code exchanged for access token
7. Token stored securely in system keyring

### 2. **API Client Layer** (✅ Implemented - Basic)

**Components:**
- `src/api/strava_client.py` - StravaAPI class

**Features:**
- OAuth token refresh handling
- Authenticated HTTP requests to Strava API v3
- Activity fetching with pagination
- Error handling and retry logic
- Token validation and cleanup

**Implemented Methods:**
- `get_activities()` - Fetch user's activities

**Pending Methods:**
- `get_activity_details()` - Full activity data
- `get_activity_streams()` - GPS coordinates and metrics

### 3. **Data Model Layer** (✅ Implemented)

**Models Created:**
- `Activity` - Strava activity with metadata
  - Basic info: id, name, type
  - Distance and time metrics
  - Heart rate data
  - Engagement metrics (kudos, comments)
  - Timestamps and timezone
  - Conversion method: `from_strava_api()`

**Pending Models:**
- `Track` - GPX track with route points
- `Project` - Session for merge operations
- `User` - Athlete profile information

### 4. **GUI Layer** (✅ Implemented - MVP)

**Modules:**
- `src/gui/main_window.py` - Primary GUI implementation

**Components Implemented:**
- `MainWindow` - Application main window (1000×700)
- `ActivityListWidget` - Activity list with formatting
- `ActivityDetailsWidget` - Activity detail panel
- `OAuthAuthenticationWorker` - Async authentication thread
- `FetchActivitiesWorker` - Async activity fetching thread

**Features:**
- Authenticate button for OAuth flow
- Fetch Activities button (requires auth)
- Activity list with:
  - Activity name
  - Type and distance
  - Start date/time
  - Click to view details
- Activity details panel showing:
  - Full activity metadata
  - Heart rate stats
  - Elevation metrics
  - Engagement metrics
- Status bar with progress updates
- Select/Clear all buttons (prepared)
- Error dialogs with helpful guidance

**UI State Management:**
- Buttons enabled/disabled based on state
- Progress bar for async operations
- Status messages during operations
- Automatic error detection and friendly guidance

**Pending Components:**
- Map widget for track visualization
- Export dialog
- Filter panel
- Merge preview

### 5. **Configuration Layer** (✅ Implemented)

**File**: `config/config.json`

**Current Configuration:**
```json
{
  "strava": {
    "client_id": "209943",
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

**Implementation:**
- `src/config/settings.py` - Config class
- Auto-detects config.json in common locations
- Dot notation access (e.g., `config.get("strava.client_id")`)
- Validation for Strava credentials

### 6. **Error Handling** (✅ Implemented)

**Custom Exceptions** (`src/exceptions/errors.py`):
- `GetTracksException` - Base exception
- `ConfigurationError` - Config-related
- `AuthenticationError` - Auth failures
- `TokenError` - Token management issues
- `APIError` - Strava API errors

**Error Handling Features:**
- Automatic token refresh on expiration
- Clear user-facing error messages
- Guidance for common issues (missing auth)
- Logging of detailed error info

### 7. **Logging & Utilities** (✅ Implemented)

**Components:**
- `src/utils/logging.py` - Logging setup
- File and console logging
- Structured log format with timestamps
- Per-module loggers

## Data Flow

### Startup
```
main.py
  └─> Config (load from config/config.json)
  └─> MainWindow
       └─> StravaAPI (create, no token yet)
       └─> Show UI with "Authenticate" button
```

### Authentication Flow
```
User clicks "Authenticate with Strava"
  └─> OAuthAuthenticationWorker (thread)
       └─> OAuthCallbackServer.start()
       └─> webbrowser.open(oauth_url)
       └─> Wait for user action...
       └─> Callback received with code
       └─> oauth.exchange_code()
       └─> StravaAPI.set_token()
       └─> TokenStore.save_token()
       └─> UI updates to show success
```

### Activity Fetch Flow
```
User clicks "Fetch Activities"
  └─> FetchActivitiesWorker (thread)
       └─> StravaAPI._ensure_token()
           └─> Check token valid
           └─> Refresh if expired
       └─> StravaAPI.get_activities()
           └─> requests.post(Strava API)
           └─> Parse response
       └─> Activity.from_strava_api() for each
       └─> ActivityListWidget.set_activities()
       └─> UI shows activity list
```

## Security Model

**Token Management:**
- OAuth tokens stored in system keyring (encrypted)
- Automatic token refresh on expiration
- Invalid tokens deleted from storage
- No credentials in config.json (redirect_uri only)

**API Communication:**
- HTTPS only (Strava enforced)
- Bearer token in Authorization header
- No sensitive data in logs
- Graceful error handling without exposing internals

**Configuration:**
- API credentials in config/config.json (git-ignored)
- User configuration persistent
- No hardcoded secrets

## Testing Architecture

**Test Structure:**
```
tests/
├── test_config.py          # Configuration loading
├── test_exceptions.py       # Exception handling
├── test_logging.py          # Logging utilities
├── test_main.py             # Entry point
├── test_oauth.py            # OAuth flow (mocked)
├── test_strava_client.py    # API client (mocked)
├── test_gui.py              # GUI components
├── test_gui_launch.py       # Full GUI test
└── test_oauth_real.py       # Real Strava auth (manual)
```

**Coverage:**
- Unit tests for all modules
- Integration tests for auth flow
- GUI component tests
- Real API test for manual verification

## Performance Considerations

**Current:**
- Activity list fetches up to 50 items per request
- Async workers for blocking operations
- Threading to prevent UI freezes

**Planned:**
- Pagination for large activity lists
- Caching of activity data
- Background sync with Strava
- Lazy loading of track details

## Extensibility Points

1. **New Filters** - Add to ActivityListWidget
2. **Export Formats** - Add export methods to Activity/Track
3. **Visualization** - Plugin map implementations
4. **Authentication** - Support other APIs
5. **Processing** - Add to track merger engine

## Known Limitations

1. **Current Phase**:
   - Basic activity list only
   - No track visualization
   - No merging capability
   - No GPX export
   - Limited filtering

2. **To Be Addressed**:
   - Track data retrieval (need Strava stream endpoints)
   - Map widget implementation
   - GPX merging algorithm
   - Multi-activity selection UI
   - Advanced filtering options