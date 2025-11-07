# Troubleshooting Guide

## Database Lock Issues

### Error: `sqlite3.OperationalError: unable to open database file`

This error occurs when the SQLite database is locked by another application.

#### Symptoms:
- Flask app fails to start with database connection error
- Error message mentions "unable to open database file"
- WAL file (`.db-wal`) exists in instance directory

#### Causes:
1. **DB Browser for SQLite** or similar tool has database open
2. Another instance of the app is running
3. Background process holding database connection
4. Crashed process left lock behind

#### Solutions:

**1. Check what's locking the database:**
```bash
./scripts/check_db_lock.sh
```

**2. Close DB Browser (or similar tools):**
- If you have DB Browser for SQLite open, close it
- Check for any SQLite viewers/editors

**3. Kill the locking process:**
```bash
# Find the process ID
lsof instance/app.db

# Kill it (replace PID with actual process ID)
kill <PID>
```

**4. If process won't die:**
```bash
# Force kill
kill -9 <PID>
```

**5. Clean up WAL files (last resort):**
```bash
# Stop all processes first!
rm instance/app.db-wal
rm instance/app.db-shm
```
⚠️ **Warning**: Only do this if no processes are using the database!

#### Prevention:
- Always close DB Browser before running the app
- Use `Ctrl+C` to stop Flask properly (don't force kill)
- Check for locks before starting: `./scripts/check_db_lock.sh`

---

## Port Already in Use

### Error: `Address already in use`

#### Solution:
```bash
# Find process using port 5000
lsof -i :5000

# Kill it
kill <PID>
```

Or use a different port:
```bash
flask run --port 5001
```

---

## Import Errors After Organization

### Error: `ModuleNotFoundError: No module named 'app'`

#### Cause:
Script moved to `scripts/` or `tests/` directory but import paths not updated.

#### Solution:
The organization feature should auto-fix this, but if it doesn't:

Add to top of file:
```python
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
```

---

## Database Corruption

### Symptoms:
- Database queries fail randomly
- Data appears corrupted
- App crashes on database access

#### Solutions:

**1. Restore from backup:**
```bash
# List available backups
ls -lh instance/app.db.backup_*

# Restore (replace timestamp with your backup)
cp instance/app.db.backup_YYYYMMDD_HHMMSS instance/app.db
```

**2. Use emergency restore (if logged out):**
- Navigate to: `/settings/emergency-restore`
- Upload a backup file
- Follow the restoration wizard

**3. Vacuum the database:**
- Go to: Settings → Files & Storage
- Click "Vacuum DB" button
- This will optimize and repair the database

---

## Storage Issues

### Disk Full

#### Check storage:
```bash
# Overall disk usage
df -h

# Project storage
du -sh /Users/codenear/codenear-project-files/Aadhith/V1
```

#### Clean up:
1. Go to Settings → Files & Storage
2. Use cleanup operations:
   - Clean temp files
   - Clean old logs
   - Clean old backups
   - Vacuum database

---

## Performance Issues

### Slow Database Queries

#### Solutions:
1. **Vacuum database**: Settings → Files & Storage → Vacuum DB
2. **Check database size**: Settings → Files & Storage (view stats)
3. **Clear old data**: Settings → Historical Data → Clear All Data (if needed)

### Slow Page Loads

#### Check:
1. Database size (large databases = slower queries)
2. Number of instruments (too many = slower loads)
3. Historical data volume

---

## Kite API Issues

### Token Expired

#### Symptoms:
- API calls fail with authentication error
- Historical data download fails
- Market data not updating

#### Solutions:
1. Go to Settings → Kite Connect
2. Click "Validate Token" to check status
3. If expired, click "Reconnect to Kite"
4. Complete OAuth flow

### Rate Limiting

#### Symptoms:
- Downloads pause frequently
- API errors about too many requests

#### Solutions:
1. Increase rate limit delay: Settings → Historical Data
2. Reduce concurrent requests
3. Wait for rate limit window to reset

---

## File Organization Issues

### Preview Shows Wrong Files

#### Solution:
Refresh the organization status:
1. Go to Settings → Files & Storage
2. Click "Preview Changes" again
3. Check the file list carefully before organizing

### Files Not Moving

#### Causes:
- Permission issues
- Files open in editor
- Git conflicts

#### Solutions:
1. Close all files in your editor
2. Check file permissions: `ls -la <file>`
3. Run preview first to see what would move

---

## Logs and Debugging

### Check Application Logs

```bash
# View recent logs
tail -f logs/app.log

# View error logs
tail -f logs/error.log

# Search for errors
grep ERROR logs/app.log
```

### Enable Debug Mode

In `.env`:
```
FLASK_ENV=development
FLASK_DEBUG=1
```

Then restart the app.

---

## Quick Diagnostic Commands

```bash
# Check database lock
./scripts/check_db_lock.sh

# Check disk space
df -h

# Check app processes
ps aux | grep python

# Check port usage
lsof -i :5000

# View recent errors
tail -n 50 logs/error.log

# Test database connection
sqlite3 instance/app.db "SELECT COUNT(*) FROM user;"
```

---

## Getting Help

If you encounter an issue not covered here:

1. Check logs: `logs/app.log` and `logs/error.log`
2. Review recent changes: `git log`
3. Check database: `./scripts/check_db_lock.sh`
4. Try emergency restore if data is corrupted
5. Create a backup before trying fixes

---

## Emergency Procedures

### Complete Reset (DESTRUCTIVE)

⚠️ **This will delete all data!** Back up first!

```bash
# 1. Stop the app
# Press Ctrl+C

# 2. Backup current database
cp instance/app.db instance/app.db.backup_$(date +%Y%m%d_%H%M%S)

# 3. Remove database
rm instance/app.db*

# 4. Restart app (will create fresh database)
python run.py
```

### Restore from Backup

```bash
# 1. Stop the app

# 2. Find backup
ls -lh instance/app.db.backup_*

# 3. Restore
cp instance/app.db.backup_YYYYMMDD_HHMMSS instance/app.db

# 4. Remove WAL files
rm instance/app.db-wal instance/app.db-shm

# 5. Restart app
python run.py
```
