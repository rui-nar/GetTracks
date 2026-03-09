# Features

## Core Features

1. **Strava Account Connection**
   - OAuth authentication with Strava API
   - Secure token storage and management
   - Handle token refresh automatically

2. **Activity Selection**
   - Fetch user's activities from Strava
   - Filter by date ranges (start date, end date)
   - Filter by activity types (run, ride, hike, etc.)
   - Filter by tags/labels (if available in Strava)
   - Advanced filters: distance, duration, elevation, etc.

3. **Track Visualization**
   - List view of selected activities with key metrics
   - Interactive map visualization of individual tracks
   - Preview merged track on map
   - Zoom, pan, and layer controls on map

4. **Track Merging**
   - Concatenate multiple GPX tracks into a single valid GPX file
   - Handle time continuity and metadata
   - Option to add waypoints or markers at merge points
   - Validate merged track for GPS navigation compatibility

5. **Export Functionality**
   - Export merged track as GPX file
   - Option to export individual tracks
   - Save project/session for later editing

## User Interface

- Desktop GUI built with Qt
- Main window with activity list, map view, and controls
- Progress indicators for API calls and processing
- Error handling with user-friendly messages
- Settings dialog for API keys and preferences

## Additional Features

- Offline mode (cache activities locally)
- Batch processing for multiple users/projects
- Undo/redo for selection changes
- Export to other formats (KML, TCX)
- Integration with GPS navigation apps