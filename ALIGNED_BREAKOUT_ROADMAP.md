# Aligned Breakout Strategy - Implementation Roadmap

## Current Status: ✅ Phase 1 Complete

**Completed:**
- ✅ Database schema (11 tables)
- ✅ SQLAlchemy models
- ✅ Database migration
- ✅ Default profile configuration
- ✅ Metrics calculation service
- ✅ Testing and verification

---

## Phase 2: Enhanced Metrics & Full Calculation (1-2 weeks)

### 2.1 RS vs Nifty 50 Calculation
**Priority:** High
**Effort:** Medium

Currently, `rs_vs_nifty50` is a placeholder. Implement actual calculation:

```python
# app/services/aligned_breakout_calculator.py

def calculate_nifty50_index_value(self, date=None):
    """
    Calculate Nifty 50 index value from constituent stocks

    Args:
        date: Date for calculation (default: today)

    Returns:
        float: Nifty 50 index value
    """
    # Get Nifty 50 constituent stocks
    # Calculate market-cap weighted index
    # Store in cache for performance
    pass

def calculate_rs_vs_nifty50(self, stock, lookback_days=90):
    """
    Calculate stock's RS vs Nifty 50

    Args:
        stock: Instrument object
        lookback_days: Period for RS calculation

    Returns:
        float: RS value (0-100)
    """
    # Get stock price performance over lookback period
    # Get Nifty 50 performance over same period
    # Calculate relative strength: (stock_perf / nifty_perf) * 50 + 50
    pass
```

**Tables to Use:**
- Read from: `historical_data` (stock prices)
- Write to: `aligned_breakout_stock_metrics.rs_vs_nifty50`
- Track history: `aligned_breakout_rs_history`

**Deliverables:**
1. Nifty 50 index calculation function
2. RS vs Nifty 50 calculation for stocks
3. Daily RS history tracking
4. Update `update_stock_metrics()` to include this calculation

---

### 2.2 Sector/SubSector Metrics Calculator
**Priority:** High
**Effort:** Medium

Extend calculator to handle sectors and subsectors:

```python
# app/services/aligned_breakout_calculator.py

class AlignedBreakoutCalculator:

    def calculate_sector_metrics(self, sector):
        """
        Calculate metrics for a sector

        Returns:
            dict with rs_vs_nifty50, current_stage, weeks_in_stage
        """
        # Get sector index value from sector_indices table
        # Calculate RS vs Nifty 50
        # Determine stage from sector's current_stage field
        # Calculate weeks in stage
        pass

    def update_sector_metrics(self, sector):
        """Update AlignedBreakoutSectorMetrics for a sector"""
        pass

    def update_all_sector_metrics(self):
        """Update metrics for all sectors and subsectors"""
        pass
```

**Tables to Use:**
- Read from: `sectors`, `sub_sectors`, `sector_indices`
- Write to: `aligned_breakout_sector_metrics`
- Track transitions: `aligned_breakout_stage_transitions`

**Deliverables:**
1. Sector metrics calculation
2. SubSector metrics calculation
3. Bulk update function for all sectors
4. Stage transition tracking for sectors

---

### 2.3 RS Trend Detection (4-Week Trend)
**Priority:** High
**Effort:** Medium

Implement RS trend analysis using historical data:

```python
# app/services/aligned_breakout_calculator.py

def detect_rs_trend(self, entity_type, entity_id, weeks=4):
    """
    Detect RS trend over specified weeks

    Args:
        entity_type: 'stock', 'sector', 'subsector'
        entity_id: ID of the entity
        weeks: Number of weeks to analyze (default: 4)

    Returns:
        str: 'improving', 'stable', 'declining'
    """
    # Query aligned_breakout_rs_history for last N weeks
    # Calculate linear regression slope
    # Classify as improving/stable/declining
    #
    # Thresholds:
    # - Improving: slope > 0.5 RS points per week
    # - Declining: slope < -0.5 RS points per week
    # - Stable: between -0.5 and 0.5
    pass

def record_daily_rs_snapshot(self):
    """Record daily RS values for all stocks/sectors/subsectors"""
    # For each stock: record rs_vs_nifty50, rs_vs_sector, rs_vs_subsector
    # For each sector/subsector: record rs_vs_nifty50
    # Insert into aligned_breakout_rs_history
    pass
```

**Tables to Use:**
- Write to: `aligned_breakout_rs_history`
- Update: `aligned_breakout_stock_metrics.rs_vs_nifty50_trend`
- Update: `aligned_breakout_sector_metrics.rs_vs_nifty50_trend`

**Deliverables:**
1. Daily RS snapshot recording
2. RS trend detection algorithm
3. Update metrics with trend classification
4. Scheduled daily job to record snapshots

---

### 2.4 Full Metrics Population
**Priority:** High
**Effort:** Low

Run metrics calculation for all NIFTY 500 stocks:

```bash
# Run full calculation (one-time)
source venv/bin/activate
python -c "
from app import create_app
from app.services.aligned_breakout_calculator import update_aligned_breakout_metrics

app = create_app()
with app.app_context():
    result = update_aligned_breakout_metrics()
    print(f'Completed: {result[\"success\"]}/{result[\"total\"]} stocks')

    if result['failed'] > 0:
        print(f'Failed: {result[\"failed_symbols\"][:20]}')  # Show first 20
"
```

**Deliverables:**
1. Full metrics for all NIFTY 500 stocks
2. Verification of data quality
3. Performance benchmarking
4. Error handling and retry logic for failed stocks

---

## Phase 3: Scanner Execution Engine (2-3 weeks)

### 3.1 Profile Criteria Matcher
**Priority:** High
**Effort:** High

Build the core scanner that matches stocks against profile criteria:

```python
# app/services/aligned_breakout_scanner.py

class AlignedBreakoutScanner:

    def __init__(self, profile_id):
        self.profile = AlignedBreakoutProfile.query.get(profile_id)
        self.results = []

    def scan(self):
        """
        Run scan against all NIFTY 500 stocks

        Returns:
            AlignedBreakoutScanResult object
        """
        # Create scan result record
        scan_result = AlignedBreakoutScanResult(
            profile_id=self.profile.id,
            status='running',
            started_at=datetime.utcnow()
        )
        db.session.add(scan_result)
        db.session.commit()

        try:
            # Get all NIFTY 500 stocks with metrics
            stocks = self._get_stocks_with_metrics()

            # For each stock, check against all criteria
            for stock in stocks:
                if self._matches_criteria(stock):
                    self._add_to_watchlist(scan_result.id, stock)

            # Update scan result
            scan_result.status = 'completed'
            scan_result.completed_at = datetime.utcnow()
            scan_result.total_stocks_scanned = len(stocks)
            scan_result.matched_stocks = len(self.results)
            db.session.commit()

            return scan_result

        except Exception as e:
            scan_result.status = 'failed'
            scan_result.error_message = str(e)
            db.session.commit()
            raise

    def _matches_criteria(self, stock):
        """Check if stock matches ALL profile criteria"""
        # Check sector alignment
        if not self._check_sector_alignment(stock):
            return False

        # Check stock stage criteria
        if not self._check_stock_stage(stock):
            return False

        # Check volume criteria
        if not self._check_volume(stock):
            return False

        # Check RS criteria
        if not self._check_relative_strength(stock):
            return False

        return True

    def _check_sector_alignment(self, stock):
        """Check sector stage and RS criteria"""
        # Get sector metrics
        # Check sector.current_stage == profile.sector_stage
        # Check sector.weeks_in_stage < profile.sector_max_weeks_in_stage
        # Check sector.rs_vs_nifty50 > profile.sector_rs_min
        # Same for subsector
        pass

    def _check_stock_stage(self, stock):
        """Check stock stage criteria"""
        metrics = stock.aligned_breakout_metrics

        # Check stage
        if metrics.current_stage != self.profile.stock_stage:
            return False

        # Check weeks in stage
        if metrics.weeks_in_stage >= self.profile.stock_max_weeks_in_stage:
            return False

        # Check price above 150 MA
        if self.profile.price_above_150ma:
            if not metrics.ma_150_value or stock.last_price <= metrics.ma_150_value:
                return False

        # Check MA slope
        if metrics.ma_150_slope < self.profile.ma_150_slope_min:
            return False

        # Check distance from 52w high
        dist = metrics.distance_from_52w_high_pct
        if dist < self.profile.distance_from_52w_high_min or \
           dist > self.profile.distance_from_52w_high_max:
            return False

        return True

    def _check_volume(self, stock):
        """Check volume criteria"""
        # Check volume_breakout_detected
        # Check accumulation_pattern_days
        pass

    def _check_relative_strength(self, stock):
        """Check RS criteria"""
        # Check rs_vs_sector, rs_vs_subsector, rs_vs_nifty50
        # Check rs_trend
        pass

    def _calculate_score(self, stock):
        """Calculate overall score for stock"""
        # Score each category 0-100
        # Apply weights
        # Return total score
        pass

    def _add_to_watchlist(self, scan_result_id, stock):
        """Add matched stock to watchlist with scoring"""
        # Calculate scores for each category
        scores = self._calculate_score(stock)

        # Create watchlist entry
        entry = AlignedBreakoutWatchlist(
            scan_result_id=scan_result_id,
            instrument_id=stock.id,
            tradingsymbol=stock.tradingsymbol,
            sector_name=stock.sub_sector_obj.sector.name,
            subsector_name=stock.sub_sector_obj.name,
            score_sector_alignment=scores['sector'],
            score_stock_stage=scores['stage'],
            score_volume=scores['volume'],
            score_rs=scores['rs'],
            score_total=scores['total'],
            # ... snapshot of current metrics
        )
        db.session.add(entry)
        self.results.append(entry)


# Convenience function
def run_aligned_breakout_scan(profile_id):
    """Run aligned breakout scan"""
    scanner = AlignedBreakoutScanner(profile_id)
    return scanner.scan()
```

**Tables to Use:**
- Read from: All `aligned_breakout_*` metrics tables
- Write to: `aligned_breakout_scan_results`, `aligned_breakout_watchlist`

**Deliverables:**
1. Complete scanner engine with all criteria checks
2. Scoring algorithm implementation
3. Watchlist population with denormalized data
4. Comprehensive logging and error handling

---

### 3.2 Scan Result Management
**Priority:** Medium
**Effort:** Low

```python
# Helper functions for managing scan results

def get_latest_scan_results(profile_id, limit=10):
    """Get latest scan results for a profile"""
    return AlignedBreakoutScanResult.query\
        .filter_by(profile_id=profile_id)\
        .order_by(AlignedBreakoutScanResult.created_at.desc())\
        .limit(limit)\
        .all()

def get_watchlist_for_scan(scan_result_id, min_score=None):
    """Get watchlist entries for a scan, optionally filtered by score"""
    query = AlignedBreakoutWatchlist.query.filter_by(scan_result_id=scan_result_id)

    if min_score:
        query = query.filter(AlignedBreakoutWatchlist.score_total >= min_score)

    return query.order_by(AlignedBreakoutWatchlist.score_total.desc()).all()
```

---

## Phase 4: API Endpoints (1 week)

### 4.1 Scanner Endpoints
**Priority:** High
**Effort:** Medium

```python
# app/aligned_breakout_routes.py

from flask import Blueprint, jsonify, request
from flask_login import login_required

aligned_bp = Blueprint('aligned_breakout', __name__, url_prefix='/aligned-breakout')


@aligned_bp.route('/profiles', methods=['GET'])
@login_required
def list_profiles():
    """List all aligned breakout profiles"""
    profiles = AlignedBreakoutProfile.query.filter_by(is_active=True).all()
    return jsonify({
        'success': True,
        'profiles': [p.to_dict() for p in profiles]
    })


@aligned_bp.route('/profiles/<int:profile_id>', methods=['GET'])
@login_required
def get_profile(profile_id):
    """Get a specific profile"""
    profile = AlignedBreakoutProfile.query.get_or_404(profile_id)
    return jsonify({
        'success': True,
        'profile': profile.to_dict()
    })


@aligned_bp.route('/scan/<int:profile_id>', methods=['POST'])
@login_required
def run_scan(profile_id):
    """Run a scan with the specified profile"""
    from app.services.aligned_breakout_scanner import run_aligned_breakout_scan

    try:
        scan_result = run_aligned_breakout_scan(profile_id)

        return jsonify({
            'success': True,
            'scan_result': scan_result.to_dict(),
            'matched_stocks': scan_result.matched_stocks
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@aligned_bp.route('/scan/<int:scan_id>/watchlist', methods=['GET'])
@login_required
def get_scan_watchlist(scan_id):
    """Get watchlist for a scan result"""
    min_score = request.args.get('min_score', type=float)

    watchlist = get_watchlist_for_scan(scan_id, min_score=min_score)

    return jsonify({
        'success': True,
        'count': len(watchlist),
        'watchlist': [w.to_dict() for w in watchlist]
    })


@aligned_bp.route('/metrics/<int:instrument_id>', methods=['GET'])
@login_required
def get_stock_metrics(instrument_id):
    """Get aligned breakout metrics for a stock"""
    metrics = AlignedBreakoutStockMetrics.query.filter_by(
        instrument_id=instrument_id
    ).first_or_404()

    return jsonify({
        'success': True,
        'metrics': metrics.to_dict()
    })
```

**Register blueprint in `app/__init__.py`:**
```python
from app.aligned_breakout_routes import aligned_bp
app.register_blueprint(aligned_bp)
```

---

## Phase 5: UI Integration (2-3 weeks)

### 5.1 Scanner Dashboard Page
**Priority:** High
**Effort:** High

Create new page: `app/templates/aligned_breakout/dashboard.html`

**Features:**
- Profile selector dropdown
- "Run Scan" button
- Real-time scan progress
- Results table with sorting/filtering
- Stock detail modal
- Export to CSV/Excel

### 5.2 Profile Management Page
**Priority:** Medium
**Effort:** Medium

Create: `app/templates/aligned_breakout/profile_manager.html`

**Features:**
- List all profiles
- Create new profile
- Edit existing profile
- Clone profile
- Delete profile
- Test profile (dry run)

### 5.3 Watchlist Viewer
**Priority:** High
**Effort:** Medium

Create: `app/templates/aligned_breakout/watchlist.html`

**Features:**
- Interactive table with all matched stocks
- Score breakdown visualization
- Filter by category scores
- Sort by any column
- Stock detail cards
- Add to personal watchlist
- Set price alerts

---

## Phase 6: Automation & Optimization (1 week)

### 6.1 Daily Automated Updates
**Priority:** High
**Effort:** Low

```bash
# Cron job to run daily at 6 PM after market close
0 18 * * 1-5 cd /path/to/V1 && source venv/bin/activate && python -c "
from app import create_app
from app.services.aligned_breakout_calculator import AlignedBreakoutCalculator

app = create_app()
with app.app_context():
    calc = AlignedBreakoutCalculator()

    # Update all stock metrics
    result = calc.update_all_stock_metrics()
    print(f'Stock metrics: {result[\"success\"]}/{result[\"total\"]}')

    # Update sector metrics
    calc.update_all_sector_metrics()

    # Record RS history snapshots
    calc.record_daily_rs_snapshot()

    # Optionally: Run auto-scans
    from app.services.aligned_breakout_scanner import run_aligned_breakout_scan
    run_aligned_breakout_scan(profile_id=1)  # Default profile
"
```

### 6.2 Performance Optimization
**Priority:** Medium
**Effort:** Medium

1. **Add database indexes** for frequently queried fields
2. **Implement caching** for expensive calculations (Nifty 50 index)
3. **Batch processing** for large datasets
4. **Query optimization** using SQLAlchemy profiling
5. **Async processing** for long-running scans

---

## Timeline Summary

| Phase | Duration | Priority |
|-------|----------|----------|
| ✅ Phase 1: Core Infrastructure | Complete | Critical |
| Phase 2: Enhanced Metrics | 1-2 weeks | High |
| Phase 3: Scanner Engine | 2-3 weeks | High |
| Phase 4: API Endpoints | 1 week | High |
| Phase 5: UI Integration | 2-3 weeks | High |
| Phase 6: Automation | 1 week | Medium |

**Total Estimated Time:** 7-10 weeks for full implementation

---

## Quick Win: Phase 2.4 (Immediate)

**You can start using the system right now with partial metrics:**

1. Run full metrics calculation for all stocks:
```bash
source venv/bin/activate && python -c "from app import create_app; from app.services.aligned_breakout_calculator import update_aligned_breakout_metrics; app = create_app(); app.app_context().push(); update_aligned_breakout_metrics()"
```

2. Query stocks manually using SQL:
```sql
-- Find stocks in early Stage 2 with positive MA slope
SELECT
    i.tradingsymbol,
    m.current_stage,
    m.weeks_in_stage,
    m.ma_150_slope,
    m.distance_from_52w_high_pct,
    m.volume_breakout_detected
FROM aligned_breakout_stock_metrics m
JOIN instruments i ON m.instrument_id = i.id
WHERE m.current_stage = 2
  AND m.weeks_in_stage < 4
  AND m.ma_150_slope > 0
  AND m.distance_from_52w_high_pct BETWEEN 10 AND 30
ORDER BY m.ma_150_slope DESC
LIMIT 20;
```

3. Build simple Python scripts to query and analyze:
```python
# Find aligned breakout candidates (manual version)
from app.models import Instrument, AlignedBreakoutStockMetrics

candidates = db.session.query(Instrument)\
    .join(AlignedBreakoutStockMetrics)\
    .filter(
        AlignedBreakoutStockMetrics.current_stage == 2,
        AlignedBreakoutStockMetrics.weeks_in_stage < 4,
        AlignedBreakoutStockMetrics.ma_150_slope > 0,
        AlignedBreakoutStockMetrics.distance_from_52w_high_pct.between(10, 30)
    )\
    .all()

for stock in candidates:
    print(f"{stock.tradingsymbol}: Stage {stock.aligned_breakout_metrics.current_stage}, "
          f"MA slope: {stock.aligned_breakout_metrics.ma_150_slope:.4f}")
```

---

## Success Criteria

**Phase 2:** ✓ All metrics calculated including RS vs Nifty 50
**Phase 3:** ✓ Scanner finds 10-50 stocks per scan matching criteria
**Phase 4:** ✓ API responds in < 2 seconds for scan requests
**Phase 5:** ✓ UI loads and displays results in < 3 seconds
**Phase 6:** ✓ Daily updates complete in < 5 minutes

---

**Current Status:** Phase 1 Complete ✅
**Next Milestone:** Phase 2 - Enhanced Metrics & Full Calculation
**Ready to Deploy:** Core infrastructure is production-ready!
