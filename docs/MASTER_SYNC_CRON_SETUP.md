# Master Sync Cron Setup Guide

**Date**: 2025-11-12
**Feature**: Automated Daily Data Synchronization

---

## Overview

This document explains how to set up automated daily execution of the Master Synchronization feature using cron. The Master Sync orchestrates all data sync and analysis tasks in sequence:

1. Historical Data Sync (Candlestick data from Kite)
2. Market Cap Fetch (NSE data)
3. Generate Historical Indices (Sector/Subsector indices)
4. Stage Analysis (Weinstein methodology for sectors/subsectors)
5. Stock Stage Analysis (Individual stock stages)
6. RS Calculation (Relative Strength for all stocks)
7. Volume Dry-Up Analysis (Volume pattern detection)

---

## Cron Endpoint

**URL**: `http://localhost:5002/api/master-sync/cron`
**Method**: GET
**Authentication**: None (IP-restricted to localhost only)
**Security**: Only accepts requests from `127.0.0.1`, `localhost`, or `::1`

### Response Format

```json
{
  "success": true,
  "message": "Master synchronization started successfully",
  "task_id": 1
}
```

Or if a sync is already running:

```json
{
  "success": false,
  "message": "A master sync task is already running",
  "task_id": 5
}
```

---

## Recommended Schedule

**Timing**: 4:00 PM IST (16:00 IST) daily
**Reason**: Indian stock market closes at 3:30 PM IST. Running at 4 PM allows:
- Market to fully settle
- All EOD data to be available from NSE
- Sufficient buffer for data availability

### IST to UTC Conversion

- **4:00 PM IST** = **10:30 AM UTC** (IST is UTC+5:30)

---

## Cron Setup Instructions

### Step 1: Open Crontab Editor

```bash
crontab -e
```

### Step 2: Add Cron Entry

Add one of the following entries based on your preference:

#### Option A: Using curl (Recommended)

```bash
# Run Master Sync daily at 4:00 PM IST (10:30 AM UTC)
30 10 * * * curl -s http://localhost:5002/api/master-sync/cron >> /Users/codenear/codenear-project-files/Aadhith/V1/logs/master-sync-cron.log 2>&1
```

#### Option B: Using wget

```bash
# Run Master Sync daily at 4:00 PM IST (10:30 AM UTC)
30 10 * * * wget -q -O - http://localhost:5002/api/master-sync/cron >> /Users/codenear/codenear-project-files/Aadhith/V1/logs/master-sync-cron.log 2>&1
```

#### Option C: With timestamp logging

```bash
# Run Master Sync daily at 4:00 PM IST (10:30 AM UTC) with timestamps
30 10 * * * echo "[$(date)] Starting Master Sync" >> /Users/codenear/codenear-project-files/Aadhith/V1/logs/master-sync-cron.log && curl -s http://localhost:5002/api/master-sync/cron >> /Users/codenear/codenear-project-files/Aadhith/V1/logs/master-sync-cron.log 2>&1
```

### Step 3: Create Log Directory

```bash
mkdir -p /Users/codenear/codenear-project-files/Aadhith/V1/logs
touch /Users/codenear/codenear-project-files/Aadhith/V1/logs/master-sync-cron.log
```

### Step 4: Verify Cron Entry

```bash
crontab -l
```

You should see your cron entry listed.

---

## Cron Syntax Explanation

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday=0)
│ │ │ │ │
* * * * * command to execute
```

**Our Entry**: `30 10 * * *`
- `30` = 30th minute
- `10` = 10th hour (10 AM UTC)
- `*` = Every day of month
- `*` = Every month
- `*` = Every day of week

---

## Alternative Schedules

### Run on Weekdays Only (Mon-Fri)

```bash
# Run Master Sync Mon-Fri at 4:00 PM IST
30 10 * * 1-5 curl -s http://localhost:5002/api/master-sync/cron >> /Users/codenear/codenear-project-files/Aadhith/V1/logs/master-sync-cron.log 2>&1
```

### Run at Different Time (e.g., 5:00 PM IST)

```bash
# Run Master Sync daily at 5:00 PM IST (11:30 AM UTC)
30 11 * * * curl -s http://localhost:5002/api/master-sync/cron >> /Users/codenear/codenear-project-files/Aadhith/V1/logs/master-sync-cron.log 2>&1
```

---

## Prerequisites

Before setting up cron, ensure:

1. **Flask Application is Running**
   ```bash
   # Check if Flask is running on port 5002
   lsof -i :5002
   ```

2. **Kite Connect is Configured**
   - API key and access token are set in Settings > Kite Connect
   - Access token is valid (refreshed daily before market open)

3. **Database is Accessible**
   ```bash
   # Verify database exists
   ls -lh /Users/codenear/codenear-project-files/Aadhith/V1/app.db
   ```

4. **Sufficient Disk Space**
   ```bash
   # Check available disk space
   df -h /Users/codenear/codenear-project-files/Aadhith/V1/
   ```

---

## Running Flask Application in Background

For cron to work, the Flask application must be running 24/7. Here are options:

### Option 1: Using Screen (Recommended for Development)

```bash
# Start a new screen session
screen -S flask-app

# Navigate to project directory
cd /Users/codenear/codenear-project-files/Aadhith/V1

# Activate virtual environment and run Flask
source venv/bin/activate
python run.py

# Detach from screen: Press Ctrl+A, then D
# Reattach to screen: screen -r flask-app
```

### Option 2: Using systemd (Recommended for Production)

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/flask-trading-app.service
```

Add the following content:

```ini
[Unit]
Description=Flask Trading Application
After=network.target

[Service]
Type=simple
User=codenear
WorkingDirectory=/Users/codenear/codenear-project-files/Aadhith/V1
Environment="PATH=/Users/codenear/codenear-project-files/Aadhith/V1/venv/bin"
ExecStart=/Users/codenear/codenear-project-files/Aadhith/V1/venv/bin/python run.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable flask-trading-app
sudo systemctl start flask-trading-app
sudo systemctl status flask-trading-app
```

### Option 3: Using nohup (Simple Background Process)

```bash
cd /Users/codenear/codenear-project-files/Aadhith/V1
nohup source venv/bin/activate && python run.py > logs/flask-app.log 2>&1 &
```

---

## Monitoring & Troubleshooting

### Check Cron Logs

```bash
# View cron execution log
tail -f /Users/codenear/codenear-project-files/Aadhith/V1/logs/master-sync-cron.log

# View last 50 lines
tail -n 50 /Users/codenear/codenear-project-files/Aadhith/V1/logs/master-sync-cron.log

# Search for errors
grep -i error /Users/codenear/codenear-project-files/Aadhith/V1/logs/master-sync-cron.log
```

### Check Flask Application Logs

```bash
# View Flask logs (if running in screen)
screen -r flask-app

# View nohup logs
tail -f /Users/codenear/codenear-project-files/Aadhith/V1/logs/flask-app.log
```

### Check Master Sync Task Status

```bash
# Query database for recent tasks
sqlite3 /Users/codenear/codenear-project-files/Aadhith/V1/app.db <<EOF
SELECT
    id,
    status,
    progress_percentage,
    current_step_name,
    started_at,
    completed_at,
    error_details
FROM master_sync_tasks
ORDER BY created_at DESC
LIMIT 10;
EOF
```

### Test Cron Endpoint Manually

```bash
# Test the endpoint
curl -v http://localhost:5002/api/master-sync/cron

# Expected response (success):
{"success":true,"message":"Master synchronization started successfully","task_id":1}

# Expected response (already running):
{"success":false,"message":"A master sync task is already running","task_id":5}
```

---

## Common Issues & Solutions

### Issue 1: Cron Job Not Executing

**Symptoms**: No log entries at scheduled time

**Solutions**:
1. Verify cron service is running:
   ```bash
   sudo systemctl status cron  # Linux
   # or
   launchctl list | grep cron  # macOS
   ```

2. Check system cron logs:
   ```bash
   grep CRON /var/log/syslog  # Linux
   # or
   log show --predicate 'process == "cron"' --last 1h  # macOS
   ```

3. Verify curl/wget is in PATH:
   ```bash
   which curl
   which wget
   ```

### Issue 2: "Connection Refused" Error

**Symptoms**: `curl: (7) Failed to connect to localhost port 5002: Connection refused`

**Solutions**:
1. Verify Flask is running:
   ```bash
   lsof -i :5002
   ```

2. Start Flask application:
   ```bash
   cd /Users/codenear/codenear-project-files/Aadhith/V1
   source venv/bin/activate
   python run.py
   ```

### Issue 3: "IP Address Unauthorized" Error

**Symptoms**: `{"success":false,"error":"Unauthorized IP address"}`

**Cause**: Request is not coming from localhost

**Solution**: Ensure cron uses `localhost` or `127.0.0.1`, not external IP:
```bash
curl http://127.0.0.1:5002/api/master-sync/cron
```

### Issue 4: Master Sync Already Running

**Symptoms**: `{"success":false,"message":"A master sync task is already running"}`

**Cause**: Previous sync hasn't completed yet

**Solutions**:
1. Check task status in web UI: Settings > Master Sync tab

2. Query database:
   ```bash
   sqlite3 /Users/codenear/codenear-project-files/Aadhith/V1/app.db "SELECT id, status, started_at FROM master_sync_tasks WHERE status='running';"
   ```

3. Cancel stuck task (if necessary):
   ```bash
   curl -X POST http://localhost:5002/settings/master-sync/cancel/<task_id>
   ```

---

## Timezone Considerations

### Setting System Timezone

Ensure your system timezone is set correctly:

```bash
# Check current timezone
timedatectl  # Linux
# or
date  # macOS

# Set timezone to IST (if needed)
sudo timedatectl set-timezone Asia/Kolkata  # Linux
# or
sudo systemsetup -settimezone Asia/Kolkata  # macOS
```

### Cron Timezone

By default, cron runs in the system's timezone. If your system is in IST:

```bash
# Run at 4:00 PM IST
0 16 * * * curl -s http://localhost:5002/api/master-sync/cron
```

If your system is in UTC but you want IST timing:

```bash
# Run at 4:00 PM IST = 10:30 AM UTC
30 10 * * * curl -s http://localhost:5002/api/master-sync/cron
```

---

## Best Practices

1. **Monitor Execution**: Check logs regularly to ensure sync completes successfully

2. **Disk Space**: Ensure sufficient disk space for database growth
   ```bash
   df -h /Users/codenear/codenear-project-files/Aadhith/V1/
   ```

3. **Backup Before Sync**: Run daily backups before master sync
   ```bash
   # Run backup at 3:45 PM IST (10:15 AM UTC), then sync at 4:00 PM IST
   15 10 * * * /Users/codenear/codenear-project-files/Aadhith/V1/scripts/backup_database.sh
   30 10 * * * curl -s http://localhost:5002/api/master-sync/cron
   ```

4. **Kite Token Refresh**: Ensure Kite access token is refreshed daily before market open

5. **Alert on Failure**: Set up email/SMS alerts for failed syncs
   ```bash
   30 10 * * * curl -s http://localhost:5002/api/master-sync/cron || echo "Master Sync Failed" | mail -s "Trading App Alert" your@email.com
   ```

6. **Log Rotation**: Prevent log files from growing too large
   ```bash
   # Add logrotate configuration
   sudo nano /etc/logrotate.d/flask-trading-app
   ```

   ```
   /Users/codenear/codenear-project-files/Aadhith/V1/logs/*.log {
       daily
       rotate 7
       compress
       missingok
       notifempty
   }
   ```

---

## Testing Cron Setup

### Test 1: Manual Execution

```bash
# Run the exact command that cron will execute
curl -s http://localhost:5002/api/master-sync/cron
```

### Test 2: Temporary Test Schedule

Add a test cron entry that runs every 5 minutes:

```bash
# Edit crontab
crontab -e

# Add test entry (runs every 5 minutes)
*/5 * * * * curl -s http://localhost:5002/api/master-sync/cron >> /tmp/master-sync-test.log 2>&1

# Wait 5 minutes, then check log
tail -f /tmp/master-sync-test.log

# Remove test entry after verification
crontab -e
```

### Test 3: Verify Sync Completion

After triggering a sync, monitor progress:

```bash
# Watch the task in real-time
watch -n 5 'curl -s http://localhost:5002/settings/master-sync/status | python3 -m json.tool'
```

---

## Summary

**Quick Setup**:

1. Create log directory:
   ```bash
   mkdir -p /Users/codenear/codenear-project-files/Aadhith/V1/logs
   ```

2. Add to crontab (`crontab -e`):
   ```bash
   30 10 * * * curl -s http://localhost:5002/api/master-sync/cron >> /Users/codenear/codenear-project-files/Aadhith/V1/logs/master-sync-cron.log 2>&1
   ```

3. Ensure Flask is running 24/7

4. Monitor logs:
   ```bash
   tail -f /Users/codenear/codenear-project-files/Aadhith/V1/logs/master-sync-cron.log
   ```

---

## Support

For issues or questions:
1. Check application logs
2. Verify Flask application is running
3. Test endpoint manually: `curl http://localhost:5002/api/master-sync/cron`
4. Check database for task status
5. Review error_details in master_sync_tasks table

---

**Last Updated**: 2025-11-12
**Version**: 1.0
