# Quick Test Guide - Historical Data Download

**All fixes completed! Follow these steps to test:**

---

## 🚀 Quick Start (2 Minutes)

### 1. Restart Flask (if needed)
```bash
# The app should have auto-reloaded, but if unsure:
# Press Ctrl+C in the terminal, then:
source venv/bin/activate && python run.py
```

### 2. Open Browser
```
http://127.0.0.1:5002
```

### 3. Start Download
1. Go to **Settings** → **Historical Data** tab
2. Click **"Start Download"**
3. Watch progress bar update!

---

## ✅ Success Indicators

**You'll know it's working when you see:**

1. **UI Updates Immediately**
   - Status changes from "Idle" to "Running"
   - Progress shows "X / 503 stocks"
   - Stock name updates as each downloads

2. **Logs Show Activity**
   ```bash
   tail -f logs/app.log
   ```
   Should show:
   ```
   Task X: Worker thread started
   Task X: Status updated to 'running'
   Task X: Found 503 stocks to download
   Task X: [1/503] Downloading RELIANCE...
   ```

3. **Database Gets Data**
   ```bash
   sqlite3 instance/app.db "SELECT COUNT(*) FROM historical_data;"
   ```
   Number should increase as download progresses

---

## 🔧 If Something Goes Wrong

### Force Reset Button
If download gets stuck:
1. Click **"Force Reset"** button
2. Confirm
3. Try starting download again

### Check Logs
```bash
# Last 50 lines:
tail -50 logs/app.log

# Search for errors:
grep -i "error\|failed" logs/app.log | tail -20

# Check database path:
grep "Using database" logs/app.log
# Should show: sqlite:///instance/app.db
```

### Verify Fixes Applied
```bash
# 1. Check database path in .env:
grep DATABASE_URL .env
# Should be: DATABASE_URL=sqlite:///instance/app.db

# 2. Check stuck task was cancelled:
sqlite3 instance/app.db "SELECT id, status FROM download_tasks WHERE id=3;"
# Should show: 3|cancelled
```

---

## 📊 Monitor Progress

### Real-Time Logs
```bash
tail -f logs/app.log | grep -i "download\|task"
```

### Check Stock Count
```bash
# How many stocks downloaded so far:
watch -n 5 "sqlite3 instance/app.db 'SELECT COUNT(*) FROM historical_data;'"
```

### View Last Downloaded Stock
```bash
sqlite3 instance/app.db "SELECT tradingsymbol, last_downloaded FROM historical_data ORDER BY last_downloaded DESC LIMIT 5;"
```

---

## 📈 Expected Timeline

- **503 stocks total**
- **At 3 req/sec:** ~3 minutes
- **At 1 req/sec:** ~8-9 minutes

Progress bar updates every 2 seconds.

---

## ✨ What Was Fixed

1. ✅ Database path corrected (`.env`)
2. ✅ Stuck task #3 cancelled
3. ✅ Date calculation fixed (using 2024, not 2025)
4. ✅ Thread startup validation added
5. ✅ Comprehensive logging added
6. ✅ Pre-flight validation (checks before starting)

**See [HISTORICAL_DATA_FIXES_APPLIED.md](HISTORICAL_DATA_FIXES_APPLIED.md) for full details.**

---

## 🎯 Success Looks Like

After completion:
```bash
sqlite3 instance/app.db "SELECT COUNT(*) FROM historical_data;"
# Output: 503

sqlite3 instance/app.db "SELECT tradingsymbol, LENGTH(candlestick_data) FROM historical_data LIMIT 3;"
# Output:
# RELIANCE|12456
# TCS|11234
# INFY|13567
```

**One row per stock with JSON data = SUCCESS!** 🎉
