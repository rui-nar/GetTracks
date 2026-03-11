# Features Overview

## Project Status

**Current Phase**: 5 - Filtering & Selection ✅
**Next Phase**: 6/7 - GPS Track Visualization & GPX Processing
**Target Phase**: 8+ - Export & Merging

## Implemented Features ✅

### 1. Strava Account Integration
- ✅ OAuth 2.0 authentication with Strava
- ✅ "Authenticate with Strava" button in GUI
- ✅ Browser-based authorization
- ✅ Secure token storage using system keyring
- ✅ Automatic token refresh on expiration
- ✅ Token validation and cleanup
- ✅ Clear error messages for auth failures

### 2. Activity Management
- ✅ Fetch activities from Strava (up to 50 per request)
- ✅ API rate limiting (100 req/15 min sliding window)
- ✅ Automatic retry on transient failures (5xx with exponential backoff)
- ✅ Automatic retry on rate-limit responses (429 with Retry-After)
- ✅ Activity data model with full metadata:
  - id, name, type
  - Distance and time metrics (moving/elapsed)
  - Elevation gain, high, low
  - Average/max speed
  - Heart rate data (when available)
  - Kudos, comments, achievements, photos
  - Privacy, commute, and manual flags
  - Timestamps and timezone
  - GPS start/end coordinates (optional)

### 3. Activity Filtering (Phase 5)
- ✅ Compact horizontal filter bar (always visible above activity list)
- ✅ Date range filter with calendar popups (enable/disable toggle)
- ✅ Activity type checkboxes (populated dynamically from loaded activities)
- ✅ Apply / Clear buttons
- ✅ Filter preserves master list — no re-fetch needed
- ✅ Map updates to match filtered set
- ✅ Status bar shows "Showing X of Y activities"

### 4. User Interface
- ✅ Main application window (1200×800 minimum)
- ✅ Layout: activity list (left) | details + map (right, vertical split)
- ✅ Activity list with:
  - Activity name, type, distance
  - Start date/time
  - Click to view details
  - Select All / Clear Selection
- ✅ Activity details panel:
  - Full metadata
  - Heart rate statistics
  - Elevation information
  - Engagement metrics
- ✅ Control buttons: Authenticate, Fetch, Select All, Clear Selection
- ✅ Status bar with colored indicator (ready/working/success/error)
- ✅ Progress indicator during async operations
- ✅ Error dialogs with helpful guidance

### 5. Map Visualization (Phase 6 — Partial)
- ✅ Interactive Folium map embedded via QWebEngineView
- ✅ Map hidden at startup (no white-box flash)
- ✅ Appears automatically when activities are loaded or selected
- ✅ Start/end markers per activity (color-coded by type)
- ✅ Overview mode: all activities on one map
- ✅ Detail mode: single activity focused view
- ✅ Multiple tile layers: OpenStreetMap, CartoDB positron, CartoDB dark_matter
- ✅ Null-safe: activities without GPS coordinates are silently skipped
- ✅ Temp file cleanup via Qt destroyed signal (not unreliable `__del__`)

### 6. Configuration Management
- ✅ config.json with Strava API credentials
- ✅ Application settings (logging, directories)
- ✅ Auto-detection of config file in common locations
- ✅ Configuration validation before GUI launch
- ✅ Dot-notation access (`config.get("strava.client_id")`)

### 7. Error Handling & Logging
- ✅ Custom exception hierarchy rooted at `GetTracksException`
- ✅ Detailed logging with timestamps
- ✅ User-friendly error messages in dialogs
- ✅ Automatic token cleanup on invalid tokens
- ✅ Guidance for common issues (missing auth, config errors)

### 8. Testing Infrastructure
- ✅ pytest framework with unittest.mock
- ✅ Unit tests for config, exceptions, logging, OAuth, API client
- ✅ Comprehensive filter engine tests (25+ cases)
- ✅ Rate limiter unit tests
- ✅ Retry logic tests (backoff, 429, 5xx, 4xx no-retry)
- ✅ GUI component tests

---

## Planned Features

### Phase 6/7 — GPS Tracks & GPX Processing
- [ ] Fetch GPS stream data via `get_activity_streams()`
- [ ] Render GPS polylines on map (not just start/end markers)
- [ ] Parse GPX files from Strava export
- [ ] Track merging algorithm (time-ordered concatenation)
- [ ] Waypoint handling and metadata preservation
- [ ] GPX validation
- [ ] Merged track preview on map
- [ ] Elevation profile display

### Phase 5 — Filtering Enhancements (Planned)
- [ ] Filter by distance (min/max)
- [ ] Filter by duration
- [ ] Filter by elevation gain
- [ ] Save and restore filter presets
- [ ] Persistent filter state between sessions

### Phase 8 — Export Functionality
- [ ] Export as GPX file
- [ ] Export dialog with options
- [ ] Export as KML (stretch goal)
- [ ] Export as TCX (stretch goal)
- [ ] Save/load project/session state

### Phase 9 — Settings
- [ ] Settings dialog for API key management
- [ ] Theme/appearance options
- [ ] Default filter preferences

### Phase 3 — Data (Pending)
- [ ] Local caching of activity data (avoid re-fetching)
- [ ] `Track` model (GPS route points)
- [ ] `Project` model (session for merge operations)
- [ ] Pagination for >50 activities

### Advanced (Phase 10+)
- [ ] Offline mode with cached activities
- [ ] Activity splitting and joining
- [ ] Track smoothing and correction
- [ ] Analytics and statistics
- [ ] GPS device integration

---

## UI Layout

### Current (Phase 5) ✅
```
┌─ Main Window (1200×800+) ──────────────────────────────────────────┐
│ ┌─ Buttons ─────────────────────────────────┐                      │
│ │ [Authenticate] [Fetch] [Select All] [Clr] │                      │
│ ├───────────────────────────────────────────┤                      │
│ │ ┌─ Filters ──────────────────────────────┐│                      │
│ │ │ [x] Date: 2024-01-01 to 2024-12-31     ││                      │
│ │ │ Types: [x]Run [x]Ride [x]Hike  [Apply] ││                      │
│ │ └────────────────────────────────────────┘│  Activity Details    │
│ │ Progress Bar (hidden when idle)           │                      │
│ │ ─────────────────────────────────────────│  ────────────────── │
│ │ Activity 1  Run  5.2km  2024-03-15 09:00 │                      │
│ │ Activity 2  Ride 22.1km 2024-03-12 07:30 │  Map (interactive)   │
│ │ ...                                       │  hidden until loaded │
│ └───────────────────────────────────────────┘                      │
│ Status: Showing 12 of 50 activities        [●]                     │
└────────────────────────────────────────────────────────────────────┘
```

### Phase 7 (GPS Tracks) 🎯
```
┌─ Main Window ──────────────────────────────────────────────────────┐
│ ┌─ Controls + Filters ──────────────────────────────────────────┐  │
│ │ [Auth][Fetch][Sel][Clr] │ Date range │ Types │ [Apply][Clear] │  │
│ ├────────────────────────────────────────────────────────────────┤  │
│ │ Activity List          │ Activity Details                      │  │
│ │ (filtered)             ├────────────────────────────────────── │  │
│ │                        │ Map with GPS polylines                │  │
│ │                        │ (elevation-coloured track)            │  │
│ └────────────────────────┴───────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### Phase 8 (Merging & Export) 📤
```
┌─ Main Window ──────────────────────────────────────────────────────┐
│ File | Edit | View | Tools | Help                                   │
│ ├─────────────────────────┬──────────────────────────────────────┐ │
│ │ Activity List (filtered)│ Preview: Merged Track on Map         │ │
│ │ [x] Activity A          │                                       │ │
│ │ [x] Activity B          ├──────────────────────────────────────┤ │
│ │ [ ] Activity C          │ Merge Settings                        │ │
│ │                         │  [Merge Selected] [Export GPX...]     │ │
│ └─────────────────────────┴──────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

---

## Feature Dependencies

```
Core (Phase 1) ✅
├─ Configuration ✅
├─ Logging ✅
└─ Exceptions ✅

Authentication & API (Phase 2) ✅
├─ OAuth Flow ✅
├─ Token Storage ✅
├─ Rate Limiting ✅
└─ Retry Logic ✅

Data Models (Phase 3 — partial) ✅
└─ Activity Model ✅

Basic GUI (Phase 4) ✅
├─ MainWindow ✅
├─ ActivityListWidget ✅
└─ ActivityDetailsWidget ✅

Filtering (Phase 5) ✅
├─ FilterCriteria ✅
├─ FilterEngine ✅
└─ FilterWidget ✅

Map Visualization (Phase 6 — partial) ✅
└─ MapWidget (markers; polylines pending) ✅

GPS Tracks & GPX (Phase 7) 🎯
├─ get_activity_streams()
├─ GPX parsing (gpxpy)
├─ Track merging
└─ Polyline rendering

Export (Phase 8) 📤
├─ GPX export
└─ Export dialog
```

## Success Criteria

### Phase 5 ✅ (Complete)
- ✅ User can filter activities by date range
- ✅ User can filter by activity type
- ✅ Map and list stay in sync with filters
- ✅ Filter state is clear and resettable

### Phase 7 (Next)
- [ ] GPS tracks visible as polylines on map
- [ ] Multiple activities can be selected for merge
- [ ] Merged track preview visible

### Phase 8 (Final)
- [ ] Merged track exportable as valid GPX
- [ ] Export quality meets GPS navigation standards

## Technical Debt & Considerations

- Pagination for >50 activities
- Activity data caching to reduce API calls
- Filter persistence between sessions
- Accessibility improvements (keyboard navigation)
- Performance with large activity lists (lazy rendering)
