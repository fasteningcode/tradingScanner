# Aligned Breakout Strategy - Quick Start Guide

## 🚀 Quick Start (5 Minutes)

### 1. Calculate Metrics for Test Stocks
```bash
source venv/bin/activate
python -c "
from app import create_app
from app.services.aligned_breakout_calculator import update_aligned_breakout_metrics

app = create_app()
with app.app_context():
    # Test with 10 stocks
    result = update_aligned_breakout_metrics(limit=10)
    print(f'✓ Success: {result[\"success\"]}/{result[\"total\"]} stocks')
"
```

### 2. View Calculated Metrics
```bash
sqlite3 instance/app.db "
SELECT
    i.tradingsymbol,
    m.week_52_high,
    m.distance_from_52w_high_pct,
    m.ma_150_value,
    m.ma_150_slope,
    m.current_stage,
    m.volume_breakout_detected
FROM aligned_breakout_stock_metrics m
JOIN instruments i ON m.instrument_id = i.id
LIMIT 5;
"
```

### 3. Check Profile Configuration
```bash
sqlite3 instance/app.db "
SELECT
    name,
    sector_stage,
    stock_stage,
    stock_max_weeks_in_stage,
    stock_rs_vs_sector_min,
    stock_rs_vs_nifty50_min
FROM aligned_breakout_profiles;
"
```

---

## 📊 Common Operations

### Calculate Metrics for All NIFTY 500 Stocks
```python
from app import create_app
from app.services.aligned_breakout_calculator import update_aligned_breakout_metrics

app = create_app()
with app.app_context():
    result = update_aligned_breakout_metrics()
    print(f"Processed: {result['total']}")
    print(f"Success: {result['success']}")
    print(f"Failed: {result['failed']}")

    if result['failed_symbols']:
        print(f"Failed symbols: {result['failed_symbols'][:10]}")  # Show first 10
```

### Query Stocks by Criteria

**Find stocks with positive MA slope (trending up):**
```python
from app.models import AlignedBreakoutStockMetrics, Instrument

stocks = AlignedBreakoutStockMetrics.query.filter(
    AlignedBreakoutStockMetrics.ma_150_slope > 0
).join(Instrument).all()

for m in stocks[:10]:
    print(f"{m.instrument.tradingsymbol}: MA slope = {m.ma_150_slope:.4f}")
```

**Find stocks with volume breakouts:**
```python
stocks = AlignedBreakoutStockMetrics.query.filter(
    AlignedBreakoutStockMetrics.volume_breakout_detected == True
).join(Instrument).all()

print(f"Found {len(stocks)} stocks with volume breakouts")
```

**Find stocks in early Stage 2 (< 4 weeks):**
```python
stocks = AlignedBreakoutStockMetrics.query.filter(
    AlignedBreakoutStockMetrics.current_stage == 2,
    AlignedBreakoutStockMetrics.weeks_in_stage < 4
).join(Instrument).all()

print(f"Found {len(stocks)} stocks in early Stage 2")
```

**Find stocks 10-30% from 52-week high:**
```python
stocks = AlignedBreakoutStockMetrics.query.filter(
    AlignedBreakoutStockMetrics.distance_from_52w_high_pct.between(10, 30)
).join(Instrument).all()

for m in stocks[:10]:
    print(f"{m.instrument.tradingsymbol}: {m.distance_from_52w_high_pct:.2f}% from high")
```

---

## 🔍 Useful Queries

### Count Metrics by Stage
```sql
SELECT
    current_stage,
    COUNT(*) as count
FROM aligned_breakout_stock_metrics
GROUP BY current_stage
ORDER BY current_stage;
```

### Top 10 Stocks by MA Slope (Strongest Uptrend)
```sql
SELECT
    i.tradingsymbol,
    m.ma_150_value,
    m.ma_150_slope,
    m.current_stage
FROM aligned_breakout_stock_metrics m
JOIN instruments i ON m.instrument_id = i.id
WHERE m.ma_150_slope IS NOT NULL
ORDER BY m.ma_150_slope DESC
LIMIT 10;
```

### Stocks with Volume Breakouts
```sql
SELECT
    i.tradingsymbol,
    m.last_volume,
    m.avg_volume_50d,
    (m.last_volume * 100.0 / m.avg_volume_50d) as volume_ratio_pct
FROM aligned_breakout_stock_metrics m
JOIN instruments i ON m.instrument_id = i.id
WHERE m.volume_breakout_detected = 1
ORDER BY volume_ratio_pct DESC;
```

### Stocks Near 52-Week High
```sql
SELECT
    i.tradingsymbol,
    m.week_52_high,
    m.distance_from_52w_high_pct,
    m.week_52_high_date
FROM aligned_breakout_stock_metrics m
JOIN instruments i ON m.instrument_id = i.id
WHERE m.distance_from_52w_high_pct < 15
ORDER BY m.distance_from_52w_high_pct ASC
LIMIT 20;
```

---

## 🎯 Profile Criteria Summary

| Criteria | Value |
|----------|-------|
| **Sector Stage** | 2 |
| **Sector Max Weeks** | 24 (< 6 months) |
| **Sector RS vs Nifty 50** | > 60 |
| **SubSector RS vs Nifty 50** | > 60 |
| **Stock Stage** | 2 |
| **Stock Max Weeks** | 4 (Early Stage 2) |
| **Price vs 150-day MA** | Above (required) |
| **150-day MA Slope** | > 0 (trending up) |
| **Distance from 52w High** | 10-30% |
| **Breakout Volume** | > 150% of 50-day avg |
| **Accumulation Days** | 3 days increasing |
| **Stock RS vs Sector** | > 70 |
| **Stock RS vs SubSector** | > 70 |
| **Stock RS vs Nifty 50** | > 65 |
| **RS Trend** | Improving (4 weeks) |

---

## 📈 Understanding the Metrics

### MA Slope Interpretation
- **Positive (> 0):** Trending up ✓
- **Negative (< 0):** Trending down ✗
- **Near zero:** Flat/consolidating

### Distance from 52-Week High
- **0-10%:** Very close to high (strong momentum)
- **10-30%:** Sweet spot for entries (room to run)
- **30-50%:** Moderate distance
- **50%+:** Far from high (potential reversal candidate)

### Volume Breakout
- **True:** Last volume > 150% of 50-day average (institutional buying)
- **False:** Normal volume

### Accumulation Pattern Days
- **3:** Perfect accumulation (volume increasing 3 consecutive days)
- **0:** No accumulation pattern detected

---

## 🛠️ Maintenance Commands

### Update All Metrics (Daily Cron Job)
```bash
# Add to crontab: Run at 6 PM on weekdays
0 18 * * 1-5  cd /path/to/V1 && source venv/bin/activate && python -c "from app import create_app; from app.services.aligned_breakout_calculator import update_aligned_breakout_metrics; app = create_app(); app.app_context().push(); update_aligned_breakout_metrics()"
```

### Verify Data Freshness
```sql
SELECT
    COUNT(*) as total_metrics,
    MAX(calculated_at) as last_calculation,
    MIN(calculated_at) as first_calculation
FROM aligned_breakout_stock_metrics;
```

### Clear Old Metrics (if needed)
```sql
DELETE FROM aligned_breakout_stock_metrics;
```

---

## 🐛 Troubleshooting

### Problem: No metrics calculated
**Check:**
```python
from app.models import HistoricalData

# Verify historical data exists
count = HistoricalData.query.filter_by(interval='day').count()
print(f"Historical data records: {count}")
```

### Problem: All calculations fail
**Check:**
```python
# Test single stock manually
from app.models import Instrument
from app.services.aligned_breakout_calculator import AlignedBreakoutCalculator

stock = Instrument.query.filter_by(is_nifty500=True).first()
calc = AlignedBreakoutCalculator()
metrics = calc.calculate_stock_metrics(stock)
print(metrics)
```

### Problem: Distance from 52w high is None
**Cause:** Need at least 252 trading days (1 year) of data
```python
from app.models import HistoricalData

hist = HistoricalData.query.filter_by(
    tradingsymbol='RELIANCE',
    interval='day'
).first()

if hist:
    candles = hist.get_candles()
    print(f"Candles available: {len(candles)}")  # Should be >= 252
```

---

## 📚 Key Files

| File | Purpose |
|------|---------|
| `app/models.py` (lines 1409-1931) | 11 model classes |
| `app/services/aligned_breakout_calculator.py` | Metrics calculation |
| `migrations/versions/add_aligned_breakout_tables.py` | Database schema |
| `instance/app.db` | SQLite database |
| `ALIGNED_BREAKOUT_README.md` | Full documentation |

---

## ✅ Quick Checklist

- [x] Database tables created (11 tables)
- [x] Models implemented in models.py
- [x] Migration completed
- [x] Default profile created
- [x] Calculation service working
- [x] Test run successful (5 stocks)
- [ ] Full metrics calculation (all NIFTY 500)
- [ ] Scanner execution engine
- [ ] API endpoints
- [ ] UI integration

---

**Ready to Use!** 🎉

Run the test calculation to verify everything works:
```bash
source venv/bin/activate
python -c "from app.services.aligned_breakout_calculator import update_aligned_breakout_metrics; from app import create_app; app = create_app(); app.app_context().push(); print(update_aligned_breakout_metrics(limit=5))"
```
