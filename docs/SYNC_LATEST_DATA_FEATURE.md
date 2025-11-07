# Sync Latest Historical Data Feature

## Overview

A new "Sync Latest Data" feature has been added to the Settings > Historical Data page that allows you to incrementally update your existing historical candlestick data from the Zerodha Kite API without downloading everything from scratch or creating duplicates.

## Implementation Details

### 1. New Files Created

#### `/app/sync_service.py` (~400 lines)
Core service handling the sync process:

**Features:**
- Incremental data sync from Kite API
- Detects latest date in existing data
- Fetches only new candles since last download
- Merges new data without creating duplicates
- Rate limiting and progress tracking
- Background thread execution

**Key Functions:**
- `start_sync_task(user_id, app)` - Initiates a new sync task
- `get_sync_status(user_id)` - Gets current sync task status
- `cancel_sync_task(task_id)` - Cancels a running sync task

**Key Class:**
- `HistoricalDataSyncer` - Handles the actual sync process in background thread
  - `_sync_stock(hist_data, settings)` - Syncs data for a single stock
  - Smart date range detection
  - Duplicate prevention using date as unique key

### 2. Modified Files

#### `/app/models.py` (+75 lines)
Added new model for tracking sync tasks:

**SyncTask Model:**
- Tracks sync progress and statistics
- Fields:
  - `interval` - Candle interval being synced
  - `status` - 'pending', 'running', 'completed', 'failed', 'cancelled'
  - `total_stocks` - Total stocks with existing data
  - `synced_stocks` - Successfully synced stocks count
  - `failed_stocks` - Failed stocks count
  - `skipped_stocks` - Already up-to-date stocks count
  - `new_candles_added` - Total new candles added
  - Timestamps for tracking
- `to_dict()` method for JSON serialization with ETA calculation

#### `/app/settings.py` (+115 lines)
Added 3 new routes for sync management:

1. `POST /settings/historical-data/sync-latest` - Start a new sync task
2. `GET /settings/historical-data/sync-status` - Get current sync status
3. `POST /settings/historical-data/cancel-sync/<task_id>` - Cancel sync task

#### `/app/templates/settings/index.html` (+350 lines)
Added complete UI for sync feature:

**UI Section:**
- New "Sync Latest Data" card in Historical Data tab
- Real-time progress tracking with:
  - Progress bar
  - Stats dashboard (Synced, Skipped, Failed, New Candles)
  - ETA calculation
  - Start time display
- Action buttons (Start Sync, Cancel Sync)

**JavaScript Functions:**
- `startSync()` - Initiates sync task
- `cancelSync()` - Cancels running sync
- `checkSyncStatus()` - Polls for status updates
- `updateSyncUI(status)` - Updates UI with progress
- `resetSyncUI()` - Resets UI to initial state
- Auto-resume sync display on page load

## How It Works

### Sync Process Flow

1. **Initialization:**
   - User clicks "Sync Latest Candles" button
   - System checks for valid Kite connection
   - Creates a new `SyncTask` in database
   - Counts existing stocks with historical data

2. **Background Sync:**
   - Launches background thread via `HistoricalDataSyncer`
   - For each stock with existing data:
     - Reads existing candles from JSON data
     - Finds the latest date in existing data
     - Calculates date range (latest_date + 1 day → today)
     - Fetches new candles from Kite API
     - Merges new candles with existing candles (no duplicates)
     - Updates database with merged data
   - Applies rate limiting based on user settings

3. **Progress Tracking:**
   - UI polls `/settings/historical-data/sync-status` every 2 seconds
   - Updates progress bar and statistics in real-time
   - Shows ETA based on average time per stock

4. **Completion:**
   - Task marked as 'completed', 'failed', or 'cancelled'
   - Shows summary of results
   - UI auto-resets after 3 seconds

### Duplicate Prevention

The sync mechanism prevents duplicates by:
1. Converting existing candles array to a dictionary keyed by date
2. Adding/updating entries from new candles (overwrites if date exists)
3. Converting back to sorted array
4. This ensures each date appears only once

### Smart Skip Logic

Stocks are skipped if:
- No existing data found
- Already up-to-date (latest_date >= today)
- Instrument not found in database

## User Interface

### Location
Settings → Historical Data → "Sync Latest Data" section

### Visual Design
- **Card Header:** Green background to distinguish from download section
- **Progress Display:** Real-time updates with animated progress bar
- **Stats Grid:** 4 stat cards showing:
  - Synced stocks (green)
  - Skipped stocks (yellow)
  - Failed stocks (red)
  - New candles added (blue)

### User Experience
- Clear description of what sync does
- Non-blocking operation (runs in background)
- Real-time progress feedback
- Automatic UI state management
- Cancellation support

## Safety Features

1. **Pre-flight Checks:**
   - Validates Kite connection
   - Checks token validity
   - Ensures historical data exists
   - Prevents multiple concurrent syncs

2. **Error Handling:**
   - Per-stock error tracking
   - Failed stocks don't stop entire sync
   - Error messages logged and displayed
   - Task status properly updated on errors

3. **Rate Limiting:**
   - Respects user's requests_per_second setting
   - Same as historical download settings
   - Prevents API throttling

4. **Data Integrity:**
   - Atomic updates per stock
   - No data loss on errors
   - Existing data preserved
   - Sorted date order maintained

## Usage Instructions

### To Sync Latest Data:

1. **Prerequisites:**
   - Must have Kite connection active
   - Must have existing historical data
   - Token must be valid

2. **Steps:**
   - Go to Settings → Historical Data
   - Scroll to "Sync Latest Data" section
   - Click "Sync Latest Candles" button
   - Monitor progress in real-time
   - Wait for completion or cancel if needed

3. **Results:**
   - View summary showing:
     - Number of stocks synced
     - Stocks skipped (already up-to-date)
     - Failed stocks (if any)
     - Total new candles added

### When to Use Sync vs Full Download:

**Use Sync when:**
- You already have historical data
- You want to update with latest candles
- You want to save time and API calls
- Your data is recent (within days/weeks)

**Use Full Download when:**
- Starting fresh (no historical data)
- Want to change date range
- Want to change candle interval
- Need to rebuild entire dataset

## Technical Details

### Database Schema

```sql
CREATE TABLE sync_tasks (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    interval VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress_percentage FLOAT DEFAULT 0.0,
    total_stocks INTEGER DEFAULT 0,
    synced_stocks INTEGER DEFAULT 0,
    failed_stocks INTEGER DEFAULT 0,
    skipped_stocks INTEGER DEFAULT 0,
    new_candles_added INTEGER DEFAULT 0,
    started_at DATETIME,
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### API Endpoints

#### Start Sync
```
POST /settings/historical-data/sync-latest
Response: {
    "success": true,
    "message": "Sync task started successfully",
    "task_id": 1
}
```

#### Get Status
```
GET /settings/historical-data/sync-status
Response: {
    "success": true,
    "status": {
        "id": 1,
        "status": "running",
        "progress_percentage": 45.5,
        "total_stocks": 500,
        "synced_stocks": 227,
        "failed_stocks": 1,
        "skipped_stocks": 10,
        "new_candles_added": 1250,
        "eta_seconds": 180,
        ...
    }
}
```

#### Cancel Sync
```
POST /settings/historical-data/cancel-sync/1
Response: {
    "success": true,
    "message": "Sync task cancelled successfully"
}
```

### Threading Model

- Main Flask thread: Handles HTTP requests
- Sync worker thread: Performs actual sync operations
- Communication via database (status updates)
- No shared memory issues
- Thread-safe database access via SQLAlchemy

## Benefits

1. **Time Savings:** Only fetches new data, not entire history
2. **API Efficiency:** Fewer API calls to Kite
3. **No Duplicates:** Smart merge ensures data integrity
4. **User Friendly:** Simple one-click operation
5. **Real-time Feedback:** See progress as it happens
6. **Flexible:** Can cancel anytime
7. **Reliable:** Comprehensive error handling

## Limitations

1. **Prerequisites:** Requires existing historical data
2. **Interval-Specific:** Syncs data for configured interval only
3. **Date-Based:** Only adds dates after latest existing date
4. **No Backfill:** Doesn't fill gaps in existing data
5. **Sequential:** Processes one stock at a time (for API rate limiting)

## Future Enhancements

Possible improvements:
- Gap detection and backfill
- Selective stock sync (choose specific stocks)
- Scheduled automatic sync
- Multi-interval sync in one operation
- Sync history/audit log
- Resume interrupted syncs
- Parallel sync with smarter rate limiting
- Notification on completion

## Files Modified Summary

```
Modified:
- app/settings.py (+115 lines)
- app/models.py (+75 lines)
- app/templates/settings/index.html (+350 lines)

Created:
- app/sync_service.py (400 lines)
- docs/SYNC_LATEST_DATA_FEATURE.md (this file)
```

## Testing

The implementation includes:
- Database table creation
- Service layer testing
- API endpoint testing
- UI interaction testing

To test:
1. Ensure you have existing historical data
2. Navigate to Settings → Historical Data
3. Use "Sync Latest Candles" button
4. Verify progress tracking works
5. Check data integrity after sync
6. Verify no duplicates created

## Conclusion

The Sync Latest Data feature provides an efficient, user-friendly way to keep historical data up-to-date without re-downloading everything. It complements the existing full download feature and gives users more control over their data management workflow.
