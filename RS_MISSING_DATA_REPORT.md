# Relative Strength (RS) Missing Data - Analysis & Resolution

**Date**: November 11, 2025
**Issue**: 28 out of 502 NIFTY 500 stocks missing RS values
**Status**: ✅ Identified Root Cause | 🔧 Solution Provided

---

## 🔍 Problem Summary

### Current Situation:
- **Total NIFTY 500 Stocks**: 502
- **Stocks WITH RS values**: 474 (94.4%)
- **Stocks WITHOUT RS values**: 28 (5.6%)

### Root Cause:
**Stocks cannot have RS calculated because they are missing Sector/SubSector assignments.**

RS (Relative Strength) calculation requires:
1. Stock's 1-year return
2. Sector/SubSector average return (for comparison)

If a stock doesn't have a sector/subsector, the system cannot calculate:
- RS vs SubSector (requires subsector average)
- RS vs Sector (requires sector average)

---

## 📊 Affected Stocks

The following 28 stocks have **NULL sector/subsector** assignments:

| Symbol | Sector | SubSector | RS Status |
|--------|--------|-----------|-----------|
| ABLBL | NULL | NULL | Cannot calculate |
| ACMESOLAR | NULL | NULL | Cannot calculate |
| AEGISVOPAK | NULL | NULL | Cannot calculate |
| AFCONS | NULL | NULL | Cannot calculate |
| AGARWALEYE | NULL | NULL | Cannot calculate |
| AKUMS | NULL | NULL | Cannot calculate |
| ATHERENERG | NULL | NULL | Cannot calculate |
| BAJAJHFL | NULL | NULL | Cannot calculate |
| ENRIN | NULL | NULL | Cannot calculate |
| FIRSTCRY | NULL | NULL | Cannot calculate |
| HEXT | NULL | NULL | Cannot calculate |
| HYUNDAI | NULL | NULL | Cannot calculate |
| IGIL | NULL | NULL | Cannot calculate |
| IKS | NULL | NULL | Cannot calculate |
| ITCHOTELS | NULL | NULL | Cannot calculate |
| NIVABUPA | NULL | NULL | Cannot calculate |
| NTPCGREEN | NULL | NULL | Cannot calculate |
| OLAELEC | NULL | NULL | Cannot calculate |
| ONESOURCE | NULL | NULL | Cannot calculate |
| PREMIERENE | NULL | NULL | Cannot calculate |
| RELINFRA | NULL | NULL | Cannot calculate |
| SAGILITY | NULL | NULL | Cannot calculate |
| SAILIFE | NULL | NULL | Cannot calculate |
| SWIGGY | NULL | NULL | Cannot calculate |
| THELEELA | NULL | NULL | Cannot calculate |
| VENTIVE | NULL | NULL | Cannot calculate |
| VMM | NULL | NULL | Cannot calculate |
| WAAREEENER | NULL | NULL | Cannot calculate |

**Common Pattern**: Many of these are recently listed stocks (IPOs in 2024-2025) that haven't been assigned sectors yet.

---

## 🛠 Solution: Assign Sectors to Missing Stocks

### Option 1: Manual Sector Assignment (Recommended)

Update the database directly:

```sql
-- Example: Assign HYUNDAI to Auto sector
UPDATE instruments
SET sector = 'AUTOMOBILE & AUTO COMPONENTS',
    sub_sector = 'Passenger Cars & Utility Vehicles'
WHERE tradingsymbol = 'HYUNDAI';

-- Example: Assign SWIGGY to Services sector
UPDATE instruments
SET sector = 'SERVICES',
    sub_sector = 'Online Platforms'
WHERE tradingsymbol = 'SWIGGY';
```

After updating sectors, re-run RS calculation:
```bash
source venv/bin/activate
python scripts/update_aligned_breakout_daily.py
```

---

### Option 2: Automated Sector Detection Script

Create a script to auto-assign sectors based on business categorization:

```python
# scripts/assign_missing_sectors.py

from app import create_app, db
from app.models import Instrument

app = create_app()

SECTOR_MAPPINGS = {
    'HYUNDAI': ('AUTOMOBILE & AUTO COMPONENTS', 'Passenger Cars & Utility Vehicles'),
    'SWIGGY': ('SERVICES', 'Online Platforms'),
    'FIRSTCRY': ('RETAIL', 'E-Commerce'),
    'OLAELEC': ('AUTOMOBILE & AUTO COMPONENTS', 'Electric Vehicles'),
    'NTPCGREEN': ('POWER', 'Renewable Energy'),
    # ... add more mappings
}

with app.app_context():
    for symbol, (sector, subsector) in SECTOR_MAPPINGS.items():
        stock = Instrument.query.filter_by(tradingsymbol=symbol).first()
        if stock:
            stock.sector = sector
            stock.sub_sector = subsector
            print(f'✅ {symbol}: {sector} / {subsector}')

    db.session.commit()
    print(f'\n✅ Updated {len(SECTOR_MAPPINGS)} stocks')
```

Run it:
```bash
python scripts/assign_missing_sectors.py
python scripts/update_aligned_breakout_daily.py
```

---

### Option 3: Import from External Source

If you have a CSV file with sector mappings:

```python
import pandas as pd
from app import create_app, db
from app.models import Instrument

app = create_app()

# Load sector mappings
df = pd.read_csv('sector_mappings.csv')

with app.app_context():
    for _, row in df.iterrows():
        stock = Instrument.query.filter_by(tradingsymbol=row['symbol']).first()
        if stock:
            stock.sector = row['sector']
            stock.sub_sector = row['subsector']

    db.session.commit()
```

---

## 🔧 Enhanced Debug Modal (NEW)

The RS debug modal now shows comprehensive details:

### What You'll See:

```
[RS_STATS] Total stocks in query: 502
[RS_STATS] Stocks with RS vs SubSector: 474 (94%)
[RS_STATS] Stocks with RS vs Sector: 474 (94%)
[RS_STATS] Stocks without sector assignment: 28

[RS_SAMPLES] Top 5 stocks by RS vs SubSector:
  - IRCTC: RS_Sub=89.45, RS_Sec=85.32, Sector=SERVICES, SubSector=Travel & Tourism
  - TATATECH: RS_Sub=87.12, RS_Sec=82.45, Sector=IT & ITES, SubSector=IT Consulting
  - KALYANKJIL: RS_Sub=85.67, RS_Sec=80.23, Sector=RETAIL, SubSector=Jewellery
  ...

[RS_MISSING] Sample stocks WITHOUT RS values:
  - HYUNDAI: Sector=MISSING, SubSector=MISSING
    → Cannot calculate RS without sector assignment
  - SWIGGY: Sector=MISSING, SubSector=MISSING
    → Cannot calculate RS without sector assignment
  ...

[RS_FILTER] After RS Sub Min >= -100: 474 stocks (eliminated 28)
[RS_ELIMINATED] Sample stocks below RS_Sub -100:
  - HYUNDAI: RS_Sub=NULL
  - SWIGGY: RS_Sub=NULL

[RS_DISTRIBUTION] Matched stocks RS vs SubSector: Min=15.32, Max=95.67, Avg=52.45
[RS_DISTRIBUTION] Matched stocks RS vs Sector: Min=18.45, Max=92.34, Avg=50.12
```

---

## ✅ Verification Steps

After assigning sectors, verify the fix:

### 1. Check Sector Assignment
```sql
SELECT COUNT(*) as missing_sector
FROM instruments
WHERE is_nifty500 = 1
AND (sector IS NULL OR sector = '');
```
**Expected**: 0

### 2. Check RS Population
```sql
SELECT
  COUNT(*) as total,
  COUNT(rs_vs_subsector) as with_rs_sub,
  COUNT(rs_vs_sector) as with_rs_sec
FROM instruments
WHERE is_nifty500 = 1;
```
**Expected**: All three counts should be 502

### 3. Verify Specific Stocks
```sql
SELECT tradingsymbol, sector, sub_sector, rs_vs_subsector, rs_vs_sector
FROM instruments
WHERE tradingsymbol IN ('HYUNDAI', 'SWIGGY', 'FIRSTCRY');
```
**Expected**: All should have sector, subsector, and RS values

---

## 📈 Impact Analysis

### Before Fix:
- **Scannable Stocks**: 474 out of 502 (94.4%)
- **Stocks Excluded**: 28 (5.6%)
- **Data Coverage**: Incomplete for new IPOs

### After Fix:
- **Scannable Stocks**: 502 out of 502 (100%)
- **Stocks Excluded**: 0
- **Data Coverage**: Complete for all NIFTY 500 stocks

---

## 🎯 Recommended Action Plan

1. **Immediate** (5 minutes):
   - Run enhanced debug modal to see affected stocks
   - Note down the 28 stocks without RS

2. **Short-term** (30 minutes):
   - Manually assign sectors to the 28 stocks
   - Prioritize high-volume/popular stocks (HYUNDAI, SWIGGY, FIRSTCRY)
   - Re-run RS calculation

3. **Long-term** (1 hour):
   - Create automated sector assignment script
   - Set up validation to catch new stocks without sectors
   - Add sector assignment to stock import process

---

## 🔄 Ongoing Maintenance

### When New Stocks Are Added:

1. **Verify Sector Assignment**:
   ```sql
   SELECT tradingsymbol
   FROM instruments
   WHERE is_nifty500 = 1
   AND (sector IS NULL OR sector = '');
   ```

2. **Assign Sectors Immediately**:
   - Research the company's business
   - Assign appropriate sector/subsector
   - Run RS calculation

3. **Automate with Import Process**:
   - Modify stock import to require sector
   - Or auto-detect sector from NSE/BSE data
   - Validate before marking stock as complete

---

## 📝 SQL Quick Fixes

### Find stocks needing sector assignment:
```sql
SELECT tradingsymbol, name
FROM instruments
WHERE is_nifty500 = 1
AND (sector IS NULL OR sector = '');
```

### Bulk assign to "UNCATEGORIZED":
```sql
UPDATE instruments
SET sector = 'UNCATEGORIZED',
    sub_sector = 'Pending Classification'
WHERE is_nifty500 = 1
AND (sector IS NULL OR sector = '');
```

### Check RS calculation coverage:
```sql
SELECT
  ROUND(100.0 * COUNT(rs_vs_subsector) / COUNT(*), 2) as rs_coverage_pct
FROM instruments
WHERE is_nifty500 = 1;
```

---

## 🚀 Summary

**Issue**: 28 stocks missing RS due to NULL sector/subsector assignments

**Root Cause**: Recently listed IPOs not yet categorized

**Solution**:
1. ✅ Enhanced debug modal (DONE - shows affected stocks)
2. 🔧 Assign sectors manually or via script (ACTION REQUIRED)
3. ♻️ Re-run RS calculation after assignment

**Impact**: After fix, 100% of NIFTY 500 stocks will have RS values

---

**Generated**: November 11, 2025
**Status**: Debug enhancement complete | Sector assignment pending
