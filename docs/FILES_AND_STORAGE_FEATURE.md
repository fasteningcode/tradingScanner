# Files & Storage Management Feature

## Overview

A new "Files & Storage" tab has been added to the Settings page that provides a comprehensive GUI for managing project files, storage, and maintenance operations.

## Implementation Details

### 1. New Files Created

#### `/app/storage_service.py` (~600 lines)
Core service handling all file and storage operations:

**Features:**
- Storage analysis and statistics
- Project organization (moving files to proper directories)
- Temporary file cleanup
- Log file rotation and cleanup
- Database backup management
- SQLite database vacuum/optimization

**Key Methods:**
- `analyze_storage()` - Analyzes disk usage across the project
- `check_organization_status()` - Checks if project needs organization
- `organize_project()` - Moves files to proper directories with dry-run support
- `clean_temp_files()` - Removes temporary files
- `clean_old_logs()` - Removes log entries older than specified days
- `clean_old_backups()` - Keeps only recent backups
- `vacuum_database()` - Optimizes SQLite database

### 2. Modified Files

#### `/app/settings.py` (+223 lines)
Added 6 new routes for storage management:

1. `GET /settings/storage/analyze` - Get storage statistics
2. `GET /settings/storage/organization-status` - Check if project is organized
3. `POST /settings/storage/organize-project` - Organize project files
4. `POST /settings/storage/clean-temp` - Clean temporary files
5. `POST /settings/storage/clean-logs` - Clean old log entries
6. `POST /settings/storage/clean-backups` - Clean old database backups
7. `POST /settings/storage/vacuum-db` - Vacuum/optimize database

#### `/app/templates/settings/index.html` (+280 lines)
Added complete UI for Files & Storage management:

**UI Sections:**
1. **Storage Analysis Dashboard** - Real-time storage statistics with refresh
2. **Project Organization** - Preview and execute file organization
3. **Cleanup Operations** - 4 cleanup cards with individual actions

**JavaScript Functions:**
- `refreshStorageStats()` - Updates storage statistics
- `checkOrganizationStatus()` - Checks and displays organization status
- `previewOrganization()` - Shows dry-run of what would be moved
- `organizeProject()` - Executes file organization
- `cleanTempFiles()` - Cleans temporary files
- `cleanLogs()` - Cleans old log entries
- `cleanBackups()` - Cleans old backups
- `vacuumDatabase()` - Optimizes database

## Features

### Storage Analysis
Displays real-time metrics:
- Database size (MB)
- Log files size
- Backup files count and size
- Temporary files count and size

### Project Organization
**What it does:**
- Moves test files (`test_*.py`) to `tests/` directory
- Moves utility scripts to `scripts/` directory
- Moves debug docs to `docs/archive/`
- Moves guides to `docs/`
- Updates Python import paths automatically

**Safety Features:**
- Preview mode (dry-run) to see changes before applying
- Idempotent - can run multiple times safely
- Checks if already organized
- Automatic import path fixing

### Cleanup Operations

#### 1. Clean Temporary Files
- Removes `temp_*.db` files
- Removes `*.tmp` files
- Removes `.pyc` files
- Removes `.DS_Store` files
- Shows space freed

#### 2. Clean Old Logs
- Removes log entries older than 7 days (configurable)
- Keeps recent logs intact
- Parses log timestamps intelligently
- Shows lines removed and space freed

#### 3. Clean Old Backups
- Keeps only the 5 most recent backups (configurable)
- Sorts by modification time
- Shows which files are kept
- Shows space freed

#### 4. Vacuum Database
- Optimizes SQLite database
- Reclaims unused space
- Brief unavailability during operation
- Shows space freed

## User Interface

### Tab Location
Settings → **Files & Storage** (between Index Management and About tabs)

### Color Coding
- **Storage Analysis**: Info (blue)
- **Project Organization**: Success (green)
- **Cleanup Operations**: Warning (yellow)
- Individual cleanup cards use appropriate colors

### User Experience
- All destructive operations require confirmation
- Progress indicators for long operations
- Real-time feedback with alerts
- Refresh buttons to update statistics
- Clear descriptions of what each operation does

## Safety Features

1. **Confirmation Dialogs**: All destructive operations require user confirmation
2. **Dry Run Mode**: Preview changes before applying (organization)
3. **Idempotent Operations**: Can run multiple times safely
4. **Error Handling**: Comprehensive error handling and logging
5. **Space Reporting**: Shows how much space will be freed
6. **File Listing**: Shows exactly which files will be affected

## Usage Instructions

### To Organize Project:
1. Go to Settings → Files & Storage
2. Check "Project Organization" section
3. Click "Preview Changes" to see what will be moved
4. Click "Organize Project" to execute
5. Confirm the action
6. Page will reload showing updated status

### To Clean Up Files:
1. Go to Settings → Files & Storage
2. Scroll to "Cleanup Operations"
3. Click the appropriate cleanup button
4. Confirm the action
5. View results in alert message
6. Storage statistics auto-refresh

### To Optimize Database:
1. Go to Settings → Files & Storage
2. Click "Vacuum DB" in Cleanup Operations
3. Confirm (warns about brief unavailability)
4. Wait for completion
5. See space freed in alert

## Technical Notes

### Import Path Updates
When organizing files, the system automatically adds this to Python files:

```python
import sys
import os

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
```

This ensures scripts and tests can still import from `app` after being moved.

### Organization Timestamp
A `.organized_timestamp` file is created in the project root to track when organization was last performed.

### Storage Service
The `StorageService` class is initialized with the project root and provides all file management functionality. It's designed to be safe and idempotent.

## Testing

The implementation is complete and ready to test. To test:

1. **Start the application:**
   ```bash
   source venv/bin/activate
   python run.py
   ```

2. **Navigate to Settings:**
   - Login to the application
   - Go to Settings page
   - Click on "Files & Storage" tab

3. **Test Each Feature:**
   - View storage statistics
   - Preview organization changes
   - Execute organization (if needed)
   - Test cleanup operations
   - Test database vacuum

## Benefits

1. **No Manual Script Running**: Everything through GUI
2. **Safe Operations**: Confirmations and dry-run modes
3. **Visual Feedback**: Real-time statistics and progress
4. **Database Safe**: No risk of database corruption
5. **Reversible**: Organization can be previewed first
6. **Logging**: All operations are logged for audit trail

## Future Enhancements

Possible additions:
- Schedule automatic cleanup
- Export storage reports
- File browser for viewing files
- Download individual backups
- Restore from backup through GUI
- Compression for old logs
- Custom cleanup rules

## Files Modified Summary

```
Modified:
- app/settings.py (+223 lines)
- app/templates/settings/index.html (+280 lines)

Created:
- app/storage_service.py (600 lines)
- docs/FILES_AND_STORAGE_FEATURE.md (this file)
```

## Conclusion

The Files & Storage feature provides a comprehensive, safe, and user-friendly way to manage project files and storage through the GUI, eliminating the need to run scripts manually and reducing the risk of database issues.
