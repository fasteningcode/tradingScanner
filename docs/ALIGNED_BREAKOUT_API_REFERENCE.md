# Aligned Breakout Strategy - API Reference

Quick reference for using the Aligned Breakout API endpoints.

---

## Base URL

```
http://localhost:5000/api/aligned-breakout
```

---

## Endpoints

### 1. Get Statistics

Get overall statistics about the system.

```http
GET /api/aligned-breakout/stats
```

**Response:**
```json
{
  "success": true,
  "stats": {
    "stocks": {
      "total": 495,
      "stage_distribution": {"1": 179, "2": 105, "3": 97, "4": 114},
      "avg_rs": 40.45
    },
    "sectors": {"total": 20},
    "subsectors": {"total": 86},
    "rs_history": {
      "total_snapshots": 586,
      "latest_date": "2025-11-09"
    }
  }
}
```

### 2. Get Stocks with Metrics

Get stocks with filtering and sorting.

```http
GET /api/aligned-breakout/stocks?stage=2&rs_min=65&limit=20&sort=rs_vs_nifty50
```

**Query Parameters:**
- `stage` (int, optional): Filter by stage (1-4)
- `rs_min` (float, optional): Minimum RS vs Nifty 50 (default: 0)
- `limit` (int, optional): Max results (default: 50)
- `sort` (string, optional): Sort field - `rs_vs_nifty50` or `ma_150_slope` (default: rs_vs_nifty50)

**Response:**
```json
{
  "success": true,
  "count": 20,
  "stocks": [
    {
      "symbol": "GVT&D",
      "price": 1234.5,
      "stage": 2,
      "weeks_in_stage": null,
      "rs_vs_nifty50": 100.0,
      "rs_trend": null,
      "ma_150_value": 1100.23,
      "ma_150_slope": 8.9087,
      "week_52_high": 1250.0,
      "distance_from_52w_high_pct": 1.24,
      "volume_breakout": true,
      "accumulation_days": 0,
      "sector": "AUTOMOTIVE & AUTO COMPONENTS",
      "subsector": "2/3 Wheelers",
      "calculated_at": "2025-11-09T20:02:25"
    }
  ]
}
```

### 3. Get Stock Details

Get detailed metrics for a specific stock.

```http
GET /api/aligned-breakout/stocks/<symbol>
```

**Example:**
```http
GET /api/aligned-breakout/stocks/RELIANCE
```

**Response:**
```json
{
  "success": true,
  "stock": {
    "symbol": "RELIANCE",
    "name": "Reliance Industries Ltd",
    "price": 2500.50,
    "exchange": "NSE",
    "sector": "OIL, GAS & ENERGY",
    "subsector": "Refineries & Marketing"
  },
  "metrics": {
    "stage": 2,
    "weeks_in_stage": null,
    "stage_entry_date": null,
    "rs_vs_nifty50": 64.84,
    "rs_trend": null,
    "ma_150_value": 2400.12,
    "ma_150_slope": 2.5,
    "week_52_high": 2750.0,
    "week_52_low": 2100.0,
    "distance_from_52w_high_pct": 9.07,
    "avg_volume_50d": 5000000,
    "last_volume": 6000000,
    "volume_breakout_detected": true,
    "accumulation_pattern_days": 0,
    "calculated_at": "2025-11-09T20:02:25"
  },
  "rs_history": [
    {"date": "2025-11-09", "rs_value": 64.84}
  ]
}
```

### 4. Get Sectors

Get all sectors with RS metrics.

```http
GET /api/aligned-breakout/sectors
```

**Response:**
```json
{
  "success": true,
  "count": 20,
  "sectors": [
    {
      "id": 1,
      "name": "BANKING & FINANCIAL SERVICES",
      "rs_vs_nifty50": 68.82,
      "rs_trend": null,
      "current_stage": null,
      "weeks_in_stage": null,
      "stock_count": 82,
      "calculated_at": "2025-11-09T19:45:12"
    }
  ]
}
```

### 5. Get SubSectors

Get subsectors with filtering.

```http
GET /api/aligned-breakout/subsectors?sector_id=1&rs_min=60
```

**Query Parameters:**
- `sector_id` (int, optional): Filter by sector
- `rs_min` (float, optional): Minimum RS vs Nifty 50 (default: 0)

**Response:**
```json
{
  "success": true,
  "count": 15,
  "subsectors": [
    {
      "id": 45,
      "name": "Private Banks",
      "sector_name": "BANKING & FINANCIAL SERVICES",
      "sector_id": 1,
      "rs_vs_nifty50": 89.71,
      "rs_trend": null,
      "current_stage": null,
      "weeks_in_stage": null,
      "stock_count": 12,
      "calculated_at": "2025-11-09T19:45:15"
    }
  ]
}
```

### 6. Get Top Performers

Get top stocks across multiple metrics.

```http
GET /api/aligned-breakout/top-performers?limit=20
```

**Query Parameters:**
- `limit` (int, optional): Max results per category (default: 20)

**Response:**
```json
{
  "success": true,
  "top_rs": [
    {
      "symbol": "GVT&D",
      "price": 1234.5,
      "stage": 2,
      "rs_vs_nifty50": 100.0,
      "rs_trend": null,
      "ma_150_slope": 8.9087
    }
  ],
  "top_uptrend": [
    {
      "symbol": "MRF",
      "price": 145000.0,
      "stage": 2,
      "rs_vs_nifty50": 100.0,
      "rs_trend": null,
      "ma_150_slope": 285.1672
    }
  ],
  "stage2_improving": []
}
```

### 7. Update Stock Metrics

Trigger full stock metrics recalculation (slow - use with caution).

```http
POST /api/aligned-breakout/update-metrics
Content-Type: application/json

{
  "limit": 10
}
```

**Response:**
```json
{
  "success": true,
  "message": "Metrics updated successfully",
  "stats": {
    "total": 10,
    "success": 10,
    "failed": 0,
    "failed_symbols": []
  }
}
```

### 8. Update RS Trends

Trigger RS trend calculation (fast - daily job).

```http
POST /api/aligned-breakout/update-rs-trends
```

**Response:**
```json
{
  "success": true,
  "message": "RS trends updated successfully",
  "stats": {
    "stocks": {"total": 502, "success": 0, "failed": 502},
    "sectors": {"total": 20, "success": 0, "failed": 20},
    "subsectors": {"total": 103, "success": 0, "failed": 103}
  }
}
```

---

## Usage Examples

### Python

```python
import requests

# Get stats
response = requests.get('http://localhost:5000/api/aligned-breakout/stats')
stats = response.json()
print(f"Total stocks: {stats['stats']['stocks']['total']}")

# Get Stage 2 stocks with RS > 65
params = {'stage': 2, 'rs_min': 65, 'limit': 20}
response = requests.get('http://localhost:5000/api/aligned-breakout/stocks', params=params)
stocks = response.json()['stocks']

for stock in stocks:
    print(f"{stock['symbol']}: RS={stock['rs_vs_nifty50']}, Slope={stock['ma_150_slope']}")

# Get stock details
response = requests.get('http://localhost:5000/api/aligned-breakout/stocks/RELIANCE')
data = response.json()
print(f"{data['stock']['name']}: RS={data['metrics']['rs_vs_nifty50']}")
```

### cURL

```bash
# Get stats
curl http://localhost:5000/api/aligned-breakout/stats

# Get Stage 2 stocks
curl "http://localhost:5000/api/aligned-breakout/stocks?stage=2&rs_min=65&limit=10"

# Get stock details
curl http://localhost:5000/api/aligned-breakout/stocks/RELIANCE

# Get top performers
curl http://localhost:5000/api/aligned-breakout/top-performers?limit=10

# Trigger RS trends update
curl -X POST http://localhost:5000/api/aligned-breakout/update-rs-trends
```

---

## Daily Automation

Use the provided script to automate daily updates:

```bash
# Full update (all metrics)
python scripts/update_aligned_breakout_daily.py

# RS trends only (fast, run daily)
python scripts/update_aligned_breakout_daily.py --rs-trends-only

# Stock metrics only
python scripts/update_aligned_breakout_daily.py --stocks-only

# Test with limited stocks
python scripts/update_aligned_breakout_daily.py --limit 10
```

**Cron Setup:**
```bash
# Edit crontab
crontab -e

# Add this line (run at 6:30 PM on weekdays):
30 18 * * 1-5 cd /path/to/V1 && source venv/bin/activate && python scripts/update_aligned_breakout_daily.py
```

---

## Key Metrics Explained

- **RS vs Nifty 50**: Relative Strength on 0-100 scale (50 = matches benchmark, >50 = outperforms)
- **RS Trend**: `improving`, `declining`, `stable` (requires 4 weeks of data)
- **Stage**: Weinstein Stage Analysis (1=Accumulation, 2=Markup, 3=Distribution, 4=Markdown)
- **MA 150 Slope**: 150-day moving average slope (positive = trending up)
- **Distance from 52w High**: % below 52-week high (lower = closer to highs)
- **Volume Breakout**: Last volume > 150% of 50-day average
- **Accumulation Days**: Consecutive days of increasing volume

---

## Current Data Status

As of Nov 9, 2025:

- **Stocks**: 495 with metrics (97% coverage)
- **Sectors**: 20 with RS values
- **SubSectors**: 86 with RS values
- **RS History Snapshots**: 586 (first day of tracking)
- **RS Trends**: Not yet available (need 4 weeks of daily data)

**Note:** RS trend analysis will become available after 4 weeks of daily RS snapshot collection.

---

## API Status Codes

- `200 OK`: Success
- `404 Not Found`: Stock/resource not found
- `500 Internal Server Error`: Server error

All successful responses have `"success": true` in the JSON body.

---

Generated: November 9, 2025
