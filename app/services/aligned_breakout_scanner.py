"""
Aligned Breakout Strategy - Scanner Execution Service

This service implements the scanner execution engine that:
- Loads profile criteria
- Filters stocks based on multi-level alignment (sector → subsector → stock)
- Scores candidates based on weighted criteria
- Populates scan results and watchlist

Author: Claude Code
"""

from app import db
from app.models import (
    Instrument, Sector, SubSector,
    AlignedBreakoutProfile, AlignedBreakoutScanResult,
    AlignedBreakoutWatchlist, AlignedBreakoutStockMetrics,
    AlignedBreakoutSectorMetrics
)
from datetime import datetime, date
from sqlalchemy import and_, or_
import logging

logger = logging.getLogger(__name__)


class AlignedBreakoutScanner:
    """Scanner execution engine for Aligned Breakout Strategy"""

    def __init__(self, profile):
        """
        Initialize scanner with a profile

        Args:
            profile: AlignedBreakoutProfile object or profile ID
        """
        if isinstance(profile, int):
            self.profile = AlignedBreakoutProfile.query.get(profile)
            if not self.profile:
                raise ValueError(f"Profile with ID {profile} not found")
        else:
            self.profile = profile

        self.today = date.today()
        self.scan_started_at = datetime.utcnow()

    def check_sector_criteria(self, sector_metrics):
        """
        Check if a sector meets profile criteria

        Args:
            sector_metrics: AlignedBreakoutSectorMetrics object

        Returns:
            bool: True if sector meets criteria
        """
        if not sector_metrics:
            return False

        # Check RS vs Nifty 50
        if sector_metrics.rs_vs_nifty50 is None:
            return False

        if sector_metrics.rs_vs_nifty50 < self.profile.sector_rs_min:
            return False

        # TODO: Check sector stage and weeks in stage when implemented
        # For now, we'll skip stage criteria for sectors

        return True

    def check_subsector_criteria(self, subsector_metrics):
        """
        Check if a subsector meets profile criteria

        Args:
            subsector_metrics: AlignedBreakoutSectorMetrics object

        Returns:
            bool: True if subsector meets criteria
        """
        if not subsector_metrics:
            return False

        # Check RS vs Nifty 50
        if subsector_metrics.rs_vs_nifty50 is None:
            return False

        if subsector_metrics.rs_vs_nifty50 < self.profile.subsector_rs_min:
            return False

        return True

    def check_stock_criteria(self, stock, stock_metrics, sector_metrics, subsector_metrics):
        """
        Check if a stock meets all profile criteria

        Args:
            stock: Instrument object
            stock_metrics: AlignedBreakoutStockMetrics object
            sector_metrics: AlignedBreakoutSectorMetrics object
            subsector_metrics: AlignedBreakoutSectorMetrics object

        Returns:
            tuple: (bool, dict) - (meets_criteria, criteria_details)
        """
        if not stock_metrics:
            return False, {'reason': 'No metrics available'}

        criteria_details = {}

        # 1. Check Stage
        if stock_metrics.current_stage != self.profile.stock_stage:
            return False, {'reason': f'Stage {stock_metrics.current_stage} != {self.profile.stock_stage}'}

        criteria_details['stage'] = stock_metrics.current_stage

        # 2. Check weeks in stage (if available)
        if stock_metrics.weeks_in_stage is not None:
            if stock_metrics.weeks_in_stage > self.profile.stock_max_weeks_in_stage:
                return False, {'reason': f'Weeks in stage {stock_metrics.weeks_in_stage} > {self.profile.stock_max_weeks_in_stage}'}
            criteria_details['weeks_in_stage'] = stock_metrics.weeks_in_stage
        else:
            # If weeks_in_stage not available, we'll allow it but note it
            criteria_details['weeks_in_stage'] = None

        # 3. Check Price vs 150-day MA
        if self.profile.price_above_150ma:
            if stock_metrics.ma_150_value is None or stock.last_price is None:
                return False, {'reason': 'Missing MA or price data'}

            if stock.last_price <= stock_metrics.ma_150_value:
                return False, {'reason': f'Price {stock.last_price} <= MA150 {stock_metrics.ma_150_value}'}

        criteria_details['price_vs_ma150'] = 'above' if stock.last_price > stock_metrics.ma_150_value else 'below'

        # 4. Check MA 150 slope
        if stock_metrics.ma_150_slope is None:
            return False, {'reason': 'Missing MA slope'}

        if stock_metrics.ma_150_slope < self.profile.ma_150_slope_min:
            return False, {'reason': f'MA slope {stock_metrics.ma_150_slope:.4f} < {self.profile.ma_150_slope_min}'}

        criteria_details['ma_150_slope'] = stock_metrics.ma_150_slope

        # 5. Check distance from 52-week high
        if stock_metrics.distance_from_52w_high_pct is None:
            return False, {'reason': 'Missing 52w high data'}

        if (stock_metrics.distance_from_52w_high_pct < self.profile.distance_from_52w_high_min or
            stock_metrics.distance_from_52w_high_pct > self.profile.distance_from_52w_high_max):
            return False, {
                'reason': f'Distance {stock_metrics.distance_from_52w_high_pct:.1f}% outside range '
                         f'{self.profile.distance_from_52w_high_min}-{self.profile.distance_from_52w_high_max}%'
            }

        criteria_details['distance_from_52w_high'] = stock_metrics.distance_from_52w_high_pct

        # 6. Check volume breakout
        if stock_metrics.last_volume is None or stock_metrics.avg_volume_50d is None:
            return False, {'reason': 'Missing volume data'}

        volume_pct = (stock_metrics.last_volume / stock_metrics.avg_volume_50d) * 100 if stock_metrics.avg_volume_50d > 0 else 0

        if volume_pct < self.profile.breakout_volume_min_pct:
            return False, {'reason': f'Volume {volume_pct:.0f}% < {self.profile.breakout_volume_min_pct}%'}

        criteria_details['volume_pct'] = volume_pct

        # 7. Check accumulation days
        if stock_metrics.accumulation_pattern_days < self.profile.accumulation_days:
            return False, {
                'reason': f'Accumulation days {stock_metrics.accumulation_pattern_days} < {self.profile.accumulation_days}'
            }

        criteria_details['accumulation_days'] = stock_metrics.accumulation_pattern_days

        # 8. Check RS vs Nifty 50
        if stock_metrics.rs_vs_nifty50 is None:
            return False, {'reason': 'Missing RS vs Nifty 50'}

        if stock_metrics.rs_vs_nifty50 < self.profile.stock_rs_vs_nifty50_min:
            return False, {'reason': f'RS {stock_metrics.rs_vs_nifty50:.1f} < {self.profile.stock_rs_vs_nifty50_min}'}

        criteria_details['rs_vs_nifty50'] = stock_metrics.rs_vs_nifty50

        # 9. Check RS trend (if required and available)
        if self.profile.rs_trend_direction and self.profile.rs_trend_direction != 'any':
            if stock_metrics.rs_vs_nifty50_trend is None:
                # RS trend not yet available (need 4 weeks of data)
                # For now, we'll allow it but note it
                criteria_details['rs_trend'] = None
            elif stock_metrics.rs_vs_nifty50_trend != self.profile.rs_trend_direction:
                return False, {
                    'reason': f'RS trend {stock_metrics.rs_vs_nifty50_trend} != {self.profile.rs_trend_direction}'
                }
            else:
                criteria_details['rs_trend'] = stock_metrics.rs_vs_nifty50_trend
        else:
            criteria_details['rs_trend'] = stock_metrics.rs_vs_nifty50_trend

        # 10. Check RS vs Sector (placeholder - will be implemented in Phase 2.4)
        # For now, skip this check
        criteria_details['rs_vs_sector'] = None

        # 11. Check RS vs SubSector (placeholder - will be implemented in Phase 2.4)
        # For now, skip this check
        criteria_details['rs_vs_subsector'] = None

        # All criteria passed
        return True, criteria_details

    def calculate_score(self, stock, stock_metrics, sector_metrics, subsector_metrics, criteria_details):
        """
        Calculate weighted score for a stock

        Args:
            stock: Instrument object
            stock_metrics: AlignedBreakoutStockMetrics object
            sector_metrics: AlignedBreakoutSectorMetrics object
            subsector_metrics: AlignedBreakoutSectorMetrics object
            criteria_details: dict from check_stock_criteria

        Returns:
            float: Weighted score (0-100)
        """
        scores = {
            'sector_alignment': 0,
            'stock_stage': 0,
            'volume': 0,
            'rs': 0
        }

        # 1. Sector Alignment Score (0-100)
        # Based on sector + subsector RS
        if sector_metrics and sector_metrics.rs_vs_nifty50:
            sector_score = sector_metrics.rs_vs_nifty50
        else:
            sector_score = 50  # Neutral if missing

        if subsector_metrics and subsector_metrics.rs_vs_nifty50:
            subsector_score = subsector_metrics.rs_vs_nifty50
        else:
            subsector_score = 50  # Neutral if missing

        scores['sector_alignment'] = (sector_score + subsector_score) / 2

        # 2. Stock Stage Score (0-100)
        # Based on weeks in stage (earlier = better) and price vs MA
        weeks_score = 100
        if criteria_details.get('weeks_in_stage') is not None:
            # Early Stage 2 is better: 0 weeks = 100, 4 weeks = 50
            weeks_score = max(0, 100 - (criteria_details['weeks_in_stage'] * 12.5))

        ma_slope_score = min(100, (criteria_details['ma_150_slope'] / 10) * 100)  # Normalize slope to 0-100

        scores['stock_stage'] = (weeks_score + ma_slope_score) / 2

        # 3. Volume Score (0-100)
        # Based on volume breakout strength and accumulation
        volume_pct = criteria_details.get('volume_pct', 150)
        # 150% = 50 points, 300%+ = 100 points
        volume_score = min(100, ((volume_pct - 150) / 150) * 50 + 50)

        accumulation_score = min(100, (criteria_details.get('accumulation_days', 0) / 3) * 100)

        scores['volume'] = (volume_score + accumulation_score) / 2

        # 4. RS Score (0-100)
        # Based on RS vs Nifty 50 and RS trend
        rs_score = criteria_details.get('rs_vs_nifty50', 50)

        # Bonus for improving trend
        trend_bonus = 0
        if criteria_details.get('rs_trend') == 'improving':
            trend_bonus = 10
        elif criteria_details.get('rs_trend') == 'stable':
            trend_bonus = 5

        scores['rs'] = min(100, rs_score + trend_bonus)

        # Calculate weighted total score
        total_score = (
            scores['sector_alignment'] * (self.profile.weight_sector_alignment / 100) +
            scores['stock_stage'] * (self.profile.weight_stock_stage / 100) +
            scores['volume'] * (self.profile.weight_volume / 100) +
            scores['rs'] * (self.profile.weight_rs / 100)
        )

        return total_score, scores

    def execute_scan(self):
        """
        Execute scanner and populate scan results

        Returns:
            dict: {
                'scan_id': int,
                'total_candidates': int,
                'passed_criteria': int,
                'failed_criteria': int,
                'execution_time': float
            }
        """
        start_time = datetime.utcnow()

        logger.info(f"Starting scan with profile: {self.profile.name}")

        # Get all NIFTY 500 stocks with metrics
        stocks_query = db.session.query(
            Instrument, AlignedBreakoutStockMetrics
        ).join(
            AlignedBreakoutStockMetrics,
            Instrument.id == AlignedBreakoutStockMetrics.instrument_id
        ).filter(
            Instrument.is_nifty500 == True
        )

        candidates = []
        total_candidates = 0
        passed_criteria = 0
        failed_criteria = 0

        for stock, stock_metrics in stocks_query.all():
            total_candidates += 1

            # Get sector and subsector
            if not stock.sub_sector_id:
                failed_criteria += 1
                continue

            subsector = SubSector.query.get(stock.sub_sector_id)
            if not subsector:
                failed_criteria += 1
                continue

            sector = Sector.query.get(subsector.sector_id)
            if not sector:
                failed_criteria += 1
                continue

            # Get sector and subsector metrics
            sector_metrics = AlignedBreakoutSectorMetrics.query.filter_by(
                entity_type='sector',
                sector_id=sector.id
            ).first()

            subsector_metrics = AlignedBreakoutSectorMetrics.query.filter_by(
                entity_type='subsector',
                subsector_id=subsector.id
            ).first()

            # Check sector criteria
            if not self.check_sector_criteria(sector_metrics):
                failed_criteria += 1
                continue

            # Check subsector criteria
            if not self.check_subsector_criteria(subsector_metrics):
                failed_criteria += 1
                continue

            # Check stock criteria
            meets_criteria, criteria_details = self.check_stock_criteria(
                stock, stock_metrics, sector_metrics, subsector_metrics
            )

            if not meets_criteria:
                failed_criteria += 1
                continue

            # Calculate score
            score, score_details = self.calculate_score(
                stock, stock_metrics, sector_metrics, subsector_metrics, criteria_details
            )

            # Add to candidates
            candidates.append({
                'stock': stock,
                'stock_metrics': stock_metrics,
                'sector': sector,
                'subsector': subsector,
                'sector_metrics': sector_metrics,
                'subsector_metrics': subsector_metrics,
                'score': score,
                'score_details': score_details,
                'criteria_details': criteria_details
            })

            passed_criteria += 1

        # Sort by score descending
        candidates.sort(key=lambda x: x['score'], reverse=True)

        logger.info(f"Scan complete: {passed_criteria} candidates found from {total_candidates} stocks")

        # Create scan result entries
        scan_results = []

        for candidate in candidates:
            result = AlignedBreakoutScanResult(
                profile_id=self.profile.id,
                instrument_id=candidate['stock'].id,
                scan_date=self.today,
                total_score=candidate['score'],
                sector_alignment_score=candidate['score_details']['sector_alignment'],
                stock_stage_score=candidate['score_details']['stock_stage'],
                volume_score=candidate['score_details']['volume'],
                rs_score=candidate['score_details']['rs'],
                meets_all_criteria=True,
                current_price=candidate['stock'].last_price,
                sector_id=candidate['sector'].id,
                subsector_id=candidate['subsector'].id,
                created_at=datetime.utcnow()
            )
            scan_results.append(result)

        # Save to database
        db.session.bulk_save_objects(scan_results)
        db.session.commit()

        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()

        logger.info(f"Scan results saved: {len(scan_results)} records")

        return {
            'total_candidates': total_candidates,
            'passed_criteria': passed_criteria,
            'failed_criteria': failed_criteria,
            'execution_time': execution_time,
            'results': candidates[:50]  # Return top 50 for display
        }

    def update_watchlist(self, max_items=20):
        """
        Update watchlist with top-scored stocks from latest scan

        Args:
            max_items: Maximum number of stocks to add to watchlist

        Returns:
            int: Number of watchlist items created
        """
        # Get latest scan results for this profile
        latest_results = AlignedBreakoutScanResult.query.filter_by(
            profile_id=self.profile.id,
            scan_date=self.today
        ).order_by(
            AlignedBreakoutScanResult.total_score.desc()
        ).limit(max_items).all()

        # Clear existing watchlist for this profile
        AlignedBreakoutWatchlist.query.filter_by(
            profile_id=self.profile.id
        ).delete()

        # Add new watchlist items
        watchlist_items = []

        for result in latest_results:
            item = AlignedBreakoutWatchlist(
                profile_id=self.profile.id,
                instrument_id=result.instrument_id,
                scan_result_id=result.id,
                added_date=self.today,
                status='active',
                entry_price=result.current_price,
                notes=f"Score: {result.total_score:.1f}",
                created_at=datetime.utcnow()
            )
            watchlist_items.append(item)

        db.session.bulk_save_objects(watchlist_items)
        db.session.commit()

        logger.info(f"Watchlist updated: {len(watchlist_items)} items")

        return len(watchlist_items)


# Convenience function for easy import
def run_aligned_breakout_scan(profile_name='Aligned Breakout Strategy - Institutional Grade'):
    """
    Run Aligned Breakout scan with default or specified profile

    Args:
        profile_name: Name of profile to use (default: Institutional Grade)

    Returns:
        dict: Scan results
    """
    profile = AlignedBreakoutProfile.query.filter_by(name=profile_name).first()

    if not profile:
        raise ValueError(f"Profile '{profile_name}' not found")

    scanner = AlignedBreakoutScanner(profile)
    results = scanner.execute_scan()

    # Update watchlist with top 20
    watchlist_count = scanner.update_watchlist(max_items=20)
    results['watchlist_items'] = watchlist_count

    return results
