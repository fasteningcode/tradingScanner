"""
Aligned Breakout Strategy - Metrics Calculation Service

This service calculates and updates all metrics required for the Aligned Breakout Strategy:
- 52-week high/low tracking
- 150-day MA values and slopes
- RS vs Nifty 50 for stocks, sectors, and subsectors
- Stage tracking and transitions
- Volume metrics
- RS trend detection

Author: Claude Code
"""

from app import db
from app.models import (
    Instrument, Sector, SubSector, HistoricalData,
    AlignedBreakoutStockMetrics, AlignedBreakoutSectorMetrics,
    AlignedBreakoutStageTransition, AlignedBreakoutRSHistory,
    AlignedBreakoutVolumeEvent, AlignedBreakout52WeekTracking,
    AlignedBreakoutMACalculation
)
from datetime import datetime, date, timedelta
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)


class AlignedBreakoutCalculator:
    """Calculator for Aligned Breakout Strategy metrics"""

    def __init__(self):
        self.today = date.today()
        self.nifty50_performance = None  # Cached Nifty 50 average performance
        self.nifty50_stocks_cache = None  # Cached list of Nifty 50 stocks

    def calculate_sma(self, candles, period):
        """Calculate Simple Moving Average"""
        if not candles or len(candles) < period:
            return None

        recent_candles = candles[-period:]
        close_prices = [c.get('close') for c in recent_candles if c.get('close') is not None]

        if len(close_prices) < period:
            return None

        return sum(close_prices) / period

    def calculate_ma_slope(self, candles, period, lookback=5):
        """
        Calculate MA slope over lookback periods

        Args:
            candles: List of candle dicts
            period: MA period (e.g., 150)
            lookback: Number of days to look back for slope calculation

        Returns:
            float: Slope (positive = trending up, negative = trending down)
        """
        if not candles or len(candles) < period + lookback:
            return None

        # Calculate MA values for the last lookback+1 days
        ma_values = []
        for i in range(lookback + 1):
            end_idx = len(candles) - i
            if end_idx >= period:
                candles_subset = candles[:end_idx]
                ma_val = self.calculate_sma(candles_subset, period)
                if ma_val is not None:
                    ma_values.append(ma_val)

        if len(ma_values) < 2:
            return None

        # Calculate slope as (most recent MA - oldest MA) / number of days
        ma_values.reverse()  # Oldest to newest
        slope = (ma_values[-1] - ma_values[0]) / len(ma_values)

        return slope

    def calculate_52week_metrics(self, stock):
        """
        Calculate 52-week high/low for a stock

        Returns:
            dict: {
                'week_52_high': float,
                'week_52_low': float,
                'week_52_high_date': date,
                'week_52_low_date': date,
                'distance_from_high_pct': float
            }
        """
        hist_data = HistoricalData.query.filter_by(
            tradingsymbol=stock.tradingsymbol,
            interval='day'
        ).first()

        if not hist_data:
            return None

        candles = hist_data.get_candles()
        if not candles or len(candles) < 252:  # ~52 weeks of trading days
            return None

        # Get last 252 trading days (52 weeks)
        recent_candles = candles[-252:]

        high_val = None
        low_val = None
        high_date = None
        low_date = None

        for candle in recent_candles:
            high = candle.get('high')
            low = candle.get('low')
            candle_date = candle.get('date')

            # Convert string date to Python date object
            if isinstance(candle_date, str):
                try:
                    candle_date = datetime.strptime(candle_date, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    continue

            if high is not None:
                if high_val is None or high > high_val:
                    high_val = high
                    high_date = candle_date

            if low is not None:
                if low_val is None or low < low_val:
                    low_val = low
                    low_date = candle_date

        current_price = candles[-1].get('close')

        if not high_val or not current_price:
            return None

        distance_pct = ((high_val - current_price) / high_val) * 100

        return {
            'week_52_high': high_val,
            'week_52_low': low_val,
            'week_52_high_date': high_date,
            'week_52_low_date': low_date,
            'distance_from_high_pct': distance_pct
        }

    def calculate_volume_metrics(self, stock):
        """
        Calculate volume metrics for a stock

        Returns:
            dict: {
                'avg_volume_50d': int,
                'last_volume': int,
                'volume_breakout_detected': bool,
                'accumulation_pattern_days': int
            }
        """
        hist_data = HistoricalData.query.filter_by(
            tradingsymbol=stock.tradingsymbol,
            interval='day'
        ).first()

        if not hist_data:
            return None

        candles = hist_data.get_candles()
        if not candles or len(candles) < 50:
            return None

        # Calculate 50-day average volume
        recent_50 = candles[-50:]
        volumes = [c.get('volume') for c in recent_50 if c.get('volume') is not None]

        if len(volumes) < 50:
            return None

        avg_volume = sum(volumes) / len(volumes)
        last_volume = candles[-1].get('volume')

        # Check for volume breakout (last volume > 150% of average)
        volume_breakout = last_volume > (avg_volume * 1.5) if last_volume else False

        # Check for accumulation pattern (volume increasing over last 3 days)
        accumulation_days = 0
        if len(candles) >= 3:
            last_3_volumes = [candles[-3].get('volume'), candles[-2].get('volume'), candles[-1].get('volume')]
            if all(v is not None for v in last_3_volumes):
                if last_3_volumes[0] < last_3_volumes[1] < last_3_volumes[2]:
                    accumulation_days = 3

        return {
            'avg_volume_50d': int(avg_volume),
            'last_volume': int(last_volume) if last_volume else None,
            'volume_breakout_detected': volume_breakout,
            'accumulation_pattern_days': accumulation_days
        }

    def get_nifty50_stocks(self):
        """
        Get list of NIFTY 50 constituent stocks

        Returns:
            list: List of Instrument objects that are NIFTY 50 constituents
        """
        if self.nifty50_stocks_cache is not None:
            return self.nifty50_stocks_cache

        # Query for NIFTY 50 stocks (using is_nifty50 flag if available, else top 50 by market cap)
        if hasattr(Instrument, 'is_nifty50'):
            nifty50_stocks = Instrument.query.filter_by(is_nifty50=True).all()
        else:
            # Fallback: Get top 50 stocks from NIFTY 500
            nifty50_stocks = Instrument.query.filter_by(
                is_nifty500=True
            ).order_by(
                Instrument.last_price.desc()  # Simple proxy for market cap
            ).limit(50).all()

        self.nifty50_stocks_cache = nifty50_stocks
        return nifty50_stocks

    def calculate_nifty50_performance(self, lookback_days=252):
        """
        Calculate Nifty 50 benchmark performance

        Uses average performance of NIFTY 50 constituent stocks as a proxy
        for the Nifty 50 index performance.

        Args:
            lookback_days: Number of days to calculate performance (default: 252 = 1 year)

        Returns:
            float: Average percentage return of Nifty 50 stocks, or None if insufficient data
        """
        if self.nifty50_performance is not None:
            return self.nifty50_performance

        nifty50_stocks = self.get_nifty50_stocks()

        if not nifty50_stocks:
            logger.warning("No NIFTY 50 stocks found")
            return None

        valid_returns = []

        for stock in nifty50_stocks:
            hist_data = HistoricalData.query.filter_by(
                tradingsymbol=stock.tradingsymbol,
                interval='day'
            ).first()

            if not hist_data:
                continue

            candles = hist_data.get_candles()
            if not candles or len(candles) < lookback_days + 1:
                continue

            # Get price from lookback_days ago and current price
            old_price = candles[-(lookback_days + 1)].get('close')
            current_price = candles[-1].get('close')

            if old_price and current_price and old_price > 0:
                pct_return = ((current_price - old_price) / old_price) * 100
                valid_returns.append(pct_return)

        if not valid_returns:
            logger.warning(f"Could not calculate Nifty 50 performance - no valid stock returns")
            return None

        # Calculate average return
        avg_return = sum(valid_returns) / len(valid_returns)

        logger.info(f"Nifty 50 avg performance ({lookback_days} days): {avg_return:.2f}% (from {len(valid_returns)} stocks)")

        self.nifty50_performance = avg_return
        return avg_return

    def calculate_rs_vs_nifty50(self, stock, lookback_days=252):
        """
        Calculate Relative Strength of stock vs Nifty 50

        RS is calculated as the difference between stock and benchmark returns,
        normalized to a 0-100 scale where:
        - 50 = stock performs same as Nifty 50
        - > 50 = stock outperforms Nifty 50 (each 1% outperformance = ~2.5 RS points)
        - < 50 = stock underperforms Nifty 50

        Args:
            stock: Instrument object
            lookback_days: Number of days for performance calculation (default: 252)

        Returns:
            float: RS value (0-100 scale), or None if calculation fails
        """
        # Get stock performance
        hist_data = HistoricalData.query.filter_by(
            tradingsymbol=stock.tradingsymbol,
            interval='day'
        ).first()

        if not hist_data:
            return None

        candles = hist_data.get_candles()
        if not candles or len(candles) < lookback_days + 1:
            return None

        old_price = candles[-(lookback_days + 1)].get('close')
        current_price = candles[-1].get('close')

        if not old_price or not current_price or old_price <= 0:
            return None

        stock_return = ((current_price - old_price) / old_price) * 100

        # Get Nifty 50 performance
        nifty50_return = self.calculate_nifty50_performance(lookback_days)

        if nifty50_return is None:
            return None

        # Calculate outperformance (stock return - benchmark return)
        outperformance = stock_return - nifty50_return

        # Normalize to 0-100 scale
        # Each 1% outperformance = 2.5 RS points
        # So ±20% outperformance covers full 0-100 range
        rs = 50 + (outperformance * 2.5)

        # Clamp to 0-100 range
        rs = max(0, min(100, rs))

        return round(rs, 2)

    def calculate_sector_performance(self, sector, lookback_days=252):
        """
        Calculate average performance of stocks in a sector

        Args:
            sector: Sector object
            lookback_days: Number of days for performance calculation (default: 252)

        Returns:
            dict: {
                'avg_return': float,
                'stock_count': int,
                'valid_stocks': list
            } or None if calculation fails
        """
        # Get all stocks in this sector
        from app.models import SubSector

        subsectors = SubSector.query.filter_by(sector_id=sector.id).all()
        subsector_ids = [ss.id for ss in subsectors]

        stocks = Instrument.query.filter(
            Instrument.sub_sector_id.in_(subsector_ids)
        ).all()

        if not stocks:
            logger.warning(f"No stocks found for sector {sector.name}")
            return None

        valid_returns = []
        valid_stock_symbols = []

        for stock in stocks:
            hist_data = HistoricalData.query.filter_by(
                tradingsymbol=stock.tradingsymbol,
                interval='day'
            ).first()

            if not hist_data:
                continue

            candles = hist_data.get_candles()
            if not candles or len(candles) < lookback_days + 1:
                continue

            old_price = candles[-(lookback_days + 1)].get('close')
            current_price = candles[-1].get('close')

            if old_price and current_price and old_price > 0:
                pct_return = ((current_price - old_price) / old_price) * 100
                valid_returns.append(pct_return)
                valid_stock_symbols.append(stock.tradingsymbol)

        if not valid_returns:
            logger.warning(f"Could not calculate sector performance for {sector.name} - no valid stock returns")
            return None

        avg_return = sum(valid_returns) / len(valid_returns)

        return {
            'avg_return': avg_return,
            'stock_count': len(valid_returns),
            'valid_stocks': valid_stock_symbols
        }

    def calculate_subsector_performance(self, subsector, lookback_days=252):
        """
        Calculate average performance of stocks in a subsector

        Args:
            subsector: SubSector object
            lookback_days: Number of days for performance calculation (default: 252)

        Returns:
            dict: {
                'avg_return': float,
                'stock_count': int,
                'valid_stocks': list
            } or None if calculation fails
        """
        # Get all stocks in this subsector
        stocks = Instrument.query.filter_by(sub_sector_id=subsector.id).all()

        if not stocks:
            logger.warning(f"No stocks found for subsector {subsector.name}")
            return None

        valid_returns = []
        valid_stock_symbols = []

        for stock in stocks:
            hist_data = HistoricalData.query.filter_by(
                tradingsymbol=stock.tradingsymbol,
                interval='day'
            ).first()

            if not hist_data:
                continue

            candles = hist_data.get_candles()
            if not candles or len(candles) < lookback_days + 1:
                continue

            old_price = candles[-(lookback_days + 1)].get('close')
            current_price = candles[-1].get('close')

            if old_price and current_price and old_price > 0:
                pct_return = ((current_price - old_price) / old_price) * 100
                valid_returns.append(pct_return)
                valid_stock_symbols.append(stock.tradingsymbol)

        if not valid_returns:
            logger.warning(f"Could not calculate subsector performance for {subsector.name} - no valid stock returns")
            return None

        avg_return = sum(valid_returns) / len(valid_returns)

        return {
            'avg_return': avg_return,
            'stock_count': len(valid_returns),
            'valid_stocks': valid_stock_symbols
        }

    def calculate_sector_rs_vs_nifty50(self, sector, lookback_days=252):
        """
        Calculate Sector RS vs Nifty 50

        Args:
            sector: Sector object
            lookback_days: Number of days for performance calculation (default: 252)

        Returns:
            float: RS value (0-100 scale), or None if calculation fails
        """
        sector_perf = self.calculate_sector_performance(sector, lookback_days)

        if not sector_perf:
            return None

        sector_return = sector_perf['avg_return']

        # Get Nifty 50 performance
        nifty50_return = self.calculate_nifty50_performance(lookback_days)

        if nifty50_return is None:
            return None

        # Calculate outperformance
        outperformance = sector_return - nifty50_return

        # Normalize to 0-100 scale (same formula as stock RS)
        rs = 50 + (outperformance * 2.5)

        # Clamp to 0-100 range
        rs = max(0, min(100, rs))

        return round(rs, 2)

    def calculate_subsector_rs_vs_nifty50(self, subsector, lookback_days=252):
        """
        Calculate SubSector RS vs Nifty 50

        Args:
            subsector: SubSector object
            lookback_days: Number of days for performance calculation (default: 252)

        Returns:
            float: RS value (0-100 scale), or None if calculation fails
        """
        subsector_perf = self.calculate_subsector_performance(subsector, lookback_days)

        if not subsector_perf:
            return None

        subsector_return = subsector_perf['avg_return']

        # Get Nifty 50 performance
        nifty50_return = self.calculate_nifty50_performance(lookback_days)

        if nifty50_return is None:
            return None

        # Calculate outperformance
        outperformance = subsector_return - nifty50_return

        # Normalize to 0-100 scale (same formula as stock RS)
        rs = 50 + (outperformance * 2.5)

        # Clamp to 0-100 range
        rs = max(0, min(100, rs))

        return round(rs, 2)

    def update_sector_metrics(self, sector):
        """
        Update or create AlignedBreakoutSectorMetrics for a sector

        Args:
            sector: Sector object

        Returns:
            AlignedBreakoutSectorMetrics object or None
        """
        # Calculate RS vs Nifty 50
        rs_nifty50 = self.calculate_sector_rs_vs_nifty50(sector, lookback_days=252)

        if rs_nifty50 is None:
            logger.warning(f"Could not calculate RS for sector {sector.name}")
            return None

        # Get sector performance
        sector_perf = self.calculate_sector_performance(sector, lookback_days=252)

        # Get or create metrics record
        metrics = AlignedBreakoutSectorMetrics.query.filter_by(
            entity_type='sector',
            sector_id=sector.id
        ).first()

        if not metrics:
            metrics = AlignedBreakoutSectorMetrics(
                entity_type='sector',
                sector_id=sector.id
            )
            db.session.add(metrics)

        # Update fields
        metrics.rs_vs_nifty50 = rs_nifty50
        metrics.avg_return_252d = sector_perf['avg_return']
        metrics.stock_count = sector_perf['stock_count']
        metrics.calculated_at = datetime.utcnow()

        try:
            db.session.commit()
            logger.info(f"Updated metrics for sector {sector.name}: RS = {rs_nifty50:.2f}")
            return metrics
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving sector metrics for {sector.name}: {str(e)}")
            return None

    def update_subsector_metrics(self, subsector):
        """
        Update or create AlignedBreakoutSectorMetrics for a subsector

        Args:
            subsector: SubSector object

        Returns:
            AlignedBreakoutSectorMetrics object or None
        """
        # Calculate RS vs Nifty 50
        rs_nifty50 = self.calculate_subsector_rs_vs_nifty50(subsector, lookback_days=252)

        if rs_nifty50 is None:
            logger.warning(f"Could not calculate RS for subsector {subsector.name}")
            return None

        # Get subsector performance
        subsector_perf = self.calculate_subsector_performance(subsector, lookback_days=252)

        # Get or create metrics record
        metrics = AlignedBreakoutSectorMetrics.query.filter_by(
            entity_type='subsector',
            subsector_id=subsector.id
        ).first()

        if not metrics:
            metrics = AlignedBreakoutSectorMetrics(
                entity_type='subsector',
                subsector_id=subsector.id
            )
            db.session.add(metrics)

        # Update fields
        metrics.rs_vs_nifty50 = rs_nifty50
        metrics.avg_return_252d = subsector_perf['avg_return']
        metrics.stock_count = subsector_perf['stock_count']
        metrics.calculated_at = datetime.utcnow()

        try:
            db.session.commit()
            logger.info(f"Updated metrics for subsector {subsector.name}: RS = {rs_nifty50:.2f}")
            return metrics
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving subsector metrics for {subsector.name}: {str(e)}")
            return None

    def update_all_sector_subsector_metrics(self):
        """
        Update metrics for all sectors and subsectors

        Returns:
            dict: Statistics about the update
        """
        from app.models import Sector, SubSector

        # Get all active sectors
        sectors = Sector.query.filter_by(is_active=True).all()
        subsectors = SubSector.query.all()

        results = {
            'sectors': {
                'total': len(sectors),
                'success': 0,
                'failed': 0,
                'failed_names': []
            },
            'subsectors': {
                'total': len(subsectors),
                'success': 0,
                'failed': 0,
                'failed_names': []
            }
        }

        logger.info(f"Starting metrics calculation for {len(sectors)} sectors and {len(subsectors)} subsectors...")

        # Update sector metrics
        for sector in sectors:
            result = self.update_sector_metrics(sector)
            if result:
                results['sectors']['success'] += 1
            else:
                results['sectors']['failed'] += 1
                results['sectors']['failed_names'].append(sector.name)

        # Update subsector metrics
        for subsector in subsectors:
            result = self.update_subsector_metrics(subsector)
            if result:
                results['subsectors']['success'] += 1
            else:
                results['subsectors']['failed'] += 1
                results['subsectors']['failed_names'].append(subsector.name)

        logger.info(f"Sector metrics: {results['sectors']['success']} success, {results['sectors']['failed']} failed")
        logger.info(f"SubSector metrics: {results['subsectors']['success']} success, {results['subsectors']['failed']} failed")

        return results

    def calculate_stock_metrics(self, stock):
        """
        Calculate all metrics for a single stock

        Args:
            stock: Instrument object

        Returns:
            dict: Metrics dictionary or None if calculation fails
        """
        try:
            hist_data = HistoricalData.query.filter_by(
                tradingsymbol=stock.tradingsymbol,
                interval='day'
            ).first()

            if not hist_data:
                logger.warning(f"No historical data for {stock.tradingsymbol}")
                return None

            candles = hist_data.get_candles()
            if not candles or len(candles) < 150:
                logger.warning(f"Insufficient data for {stock.tradingsymbol}: {len(candles) if candles else 0} candles")
                return None

            metrics = {}

            # Get current price from latest candle
            latest_candle = candles[-1]
            current_price = latest_candle.get('close', 0.0)

            # Update instrument last_price
            if current_price and current_price > 0:
                stock.last_price = current_price

            # Calculate 52-week metrics
            week_52_metrics = self.calculate_52week_metrics(stock)
            if week_52_metrics:
                metrics.update(week_52_metrics)

            # Calculate 150-day MA and slope
            ma_150 = self.calculate_sma(candles, 150)
            if ma_150:
                metrics['ma_150_value'] = ma_150
                metrics['ma_150_slope'] = self.calculate_ma_slope(candles, 150, lookback=10)

            # Calculate volume metrics
            volume_metrics = self.calculate_volume_metrics(stock)
            if volume_metrics:
                metrics.update(volume_metrics)

            # Get current stage (from Instrument table)
            metrics['current_stage'] = stock.current_stage

            # Calculate weeks in stage (if stage_updated_at is available)
            if stock.stage_updated_at:
                days_in_stage = (datetime.utcnow() - stock.stage_updated_at).days
                metrics['weeks_in_stage'] = days_in_stage // 7
                metrics['stage_entry_date'] = stock.stage_updated_at.date()
            else:
                metrics['weeks_in_stage'] = None
                metrics['stage_entry_date'] = None

            # RS vs Nifty 50 - Calculate using 252-day (1 year) performance
            rs_nifty50 = self.calculate_rs_vs_nifty50(stock, lookback_days=252)
            metrics['rs_vs_nifty50'] = rs_nifty50

            # Determine RS trend (placeholder for now - will be enhanced with historical RS tracking)
            # For now, we'll set it as None - Phase 2.3 will implement full trend detection
            metrics['rs_vs_nifty50_trend'] = None

            metrics['calculated_at'] = datetime.utcnow()

            return metrics

        except Exception as e:
            logger.error(f"Error calculating metrics for {stock.tradingsymbol}: {str(e)}")
            return None

    def update_stock_metrics(self, stock):
        """
        Update or create AlignedBreakoutStockMetrics for a stock

        Args:
            stock: Instrument object

        Returns:
            AlignedBreakoutStockMetrics object or None
        """
        metrics_data = self.calculate_stock_metrics(stock)
        if not metrics_data:
            return None

        # Get or create metrics record
        metrics = AlignedBreakoutStockMetrics.query.filter_by(instrument_id=stock.id).first()

        if not metrics:
            metrics = AlignedBreakoutStockMetrics(instrument_id=stock.id)
            db.session.add(metrics)

        # Update all fields
        for key, value in metrics_data.items():
            if hasattr(metrics, key):
                setattr(metrics, key, value)

        try:
            db.session.commit()
            logger.info(f"Updated metrics for {stock.tradingsymbol}")
            return metrics
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving metrics for {stock.tradingsymbol}: {str(e)}")
            return None

    def update_all_stock_metrics(self, limit=None):
        """
        Update metrics for all NIFTY 500 stocks

        Args:
            limit: Optional limit on number of stocks to process (for testing)

        Returns:
            dict: {
                'total': int,
                'success': int,
                'failed': int,
                'failed_symbols': list
            }
        """
        query = Instrument.query.filter_by(is_nifty500=True)

        if limit:
            query = query.limit(limit)

        stocks = query.all()

        total = len(stocks)
        success = 0
        failed = 0
        failed_symbols = []

        logger.info(f"Starting metrics calculation for {total} stocks...")

        for idx, stock in enumerate(stocks, 1):
            if idx % 50 == 0:
                logger.info(f"Progress: {idx}/{total} stocks processed")

            result = self.update_stock_metrics(stock)

            if result:
                success += 1
            else:
                failed += 1
                failed_symbols.append(stock.tradingsymbol)

        logger.info(f"Metrics calculation complete: {success} success, {failed} failed")

        return {
            'total': total,
            'success': success,
            'failed': failed,
            'failed_symbols': failed_symbols
        }

    def store_rs_history_snapshot(self, entity_type, entity_id, rs_value, sector_id=None, subsector_id=None, instrument_id=None):
        """
        Store a daily RS snapshot in the history table

        Args:
            entity_type: 'stock', 'sector', or 'subsector'
            entity_id: ID of the entity
            rs_value: Current RS value
            sector_id: Sector ID (for sector entities)
            subsector_id: SubSector ID (for subsector entities)
            instrument_id: Instrument ID (for stock entities)

        Returns:
            AlignedBreakoutRSHistory object or None
        """
        if rs_value is None:
            return None

        # Check if snapshot already exists for today
        existing = AlignedBreakoutRSHistory.query.filter_by(
            entity_type=entity_type,
            calculated_date=self.today
        )

        if entity_type == 'stock' and instrument_id:
            existing = existing.filter_by(instrument_id=instrument_id)
        elif entity_type == 'sector' and sector_id:
            existing = existing.filter_by(sector_id=sector_id)
        elif entity_type == 'subsector' and subsector_id:
            existing = existing.filter_by(subsector_id=subsector_id)

        existing = existing.first()

        if existing:
            # Update existing snapshot
            existing.rs_vs_nifty50 = rs_value
            existing.created_at = datetime.utcnow()
            snapshot = existing
        else:
            # Create new snapshot
            snapshot = AlignedBreakoutRSHistory(
                entity_type=entity_type,
                sector_id=sector_id,
                subsector_id=subsector_id,
                instrument_id=instrument_id,
                calculated_date=self.today,
                rs_vs_nifty50=rs_value,
                created_at=datetime.utcnow()
            )
            db.session.add(snapshot)

        try:
            db.session.commit()
            return snapshot
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error storing RS history snapshot: {str(e)}")
            return None

    def calculate_rs_trend(self, entity_type, entity_id, lookback_weeks=4):
        """
        Calculate RS trend over the past N weeks

        Analyzes historical RS snapshots to determine if RS is:
        - 'improving': RS is trending upward
        - 'declining': RS is trending downward
        - 'stable': RS is relatively flat

        Args:
            entity_type: 'stock', 'sector', or 'subsector'
            entity_id: ID of the entity (instrument_id, sector_id, or subsector_id)
            lookback_weeks: Number of weeks to analyze (default: 4)

        Returns:
            str: 'improving', 'declining', 'stable', or None
        """
        # Get historical RS snapshots
        cutoff_date = self.today - timedelta(weeks=lookback_weeks)

        query = AlignedBreakoutRSHistory.query.filter(
            AlignedBreakoutRSHistory.entity_type == entity_type,
            AlignedBreakoutRSHistory.calculated_date >= cutoff_date,
            AlignedBreakoutRSHistory.calculated_date <= self.today
        )

        if entity_type == 'stock':
            query = query.filter_by(instrument_id=entity_id)
        elif entity_type == 'sector':
            query = query.filter_by(sector_id=entity_id)
        elif entity_type == 'subsector':
            query = query.filter_by(subsector_id=entity_id)

        snapshots = query.order_by(AlignedBreakoutRSHistory.calculated_date.asc()).all()

        if len(snapshots) < 2:
            # Not enough data for trend analysis
            return None

        # Calculate linear regression slope
        rs_values = [s.rs_vs_nifty50 for s in snapshots]
        n = len(rs_values)

        # Simple linear regression: y = mx + b
        # Calculate slope (m)
        x_values = list(range(n))  # 0, 1, 2, ... n-1
        x_mean = sum(x_values) / n
        y_mean = sum(rs_values) / n

        numerator = sum((x_values[i] - x_mean) * (rs_values[i] - y_mean) for i in range(n))
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 'stable'

        slope = numerator / denominator

        # Determine trend based on slope
        # Normalize slope per week (divide by number of weeks)
        slope_per_week = slope / lookback_weeks if lookback_weeks > 0 else 0

        # Thresholds:
        # - Improving: RS increasing by > 1 point per week on average
        # - Declining: RS decreasing by > 1 point per week on average
        # - Stable: Change < 1 point per week
        if slope_per_week > 1.0:
            return 'improving'
        elif slope_per_week < -1.0:
            return 'declining'
        else:
            return 'stable'

    def update_stock_rs_trend(self, stock):
        """
        Update RS trend for a stock based on historical snapshots

        Args:
            stock: Instrument object

        Returns:
            str: Trend ('improving', 'declining', 'stable') or None
        """
        # Get current RS value
        metrics = AlignedBreakoutStockMetrics.query.filter_by(instrument_id=stock.id).first()

        if not metrics or metrics.rs_vs_nifty50 is None:
            return None

        # Store current RS snapshot
        self.store_rs_history_snapshot(
            entity_type='stock',
            entity_id=stock.id,
            rs_value=metrics.rs_vs_nifty50,
            instrument_id=stock.id
        )

        # Calculate trend
        trend = self.calculate_rs_trend('stock', stock.id, lookback_weeks=4)

        # Update metrics record
        if trend:
            metrics.rs_vs_nifty50_trend = trend
            try:
                db.session.commit()
                logger.info(f"Updated RS trend for {stock.tradingsymbol}: {trend}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating RS trend: {str(e)}")

        return trend

    def update_sector_rs_trend(self, sector):
        """
        Update RS trend for a sector based on historical snapshots

        Args:
            sector: Sector object

        Returns:
            str: Trend ('improving', 'declining', 'stable') or None
        """
        # Get current RS value
        metrics = AlignedBreakoutSectorMetrics.query.filter_by(
            entity_type='sector',
            sector_id=sector.id
        ).first()

        if not metrics or metrics.rs_vs_nifty50 is None:
            return None

        # Store current RS snapshot
        self.store_rs_history_snapshot(
            entity_type='sector',
            entity_id=sector.id,
            rs_value=metrics.rs_vs_nifty50,
            sector_id=sector.id
        )

        # Calculate trend
        trend = self.calculate_rs_trend('sector', sector.id, lookback_weeks=4)

        # Update metrics record
        if trend:
            metrics.rs_vs_nifty50_trend = trend
            try:
                db.session.commit()
                logger.info(f"Updated RS trend for sector {sector.name}: {trend}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating RS trend: {str(e)}")

        return trend

    def update_subsector_rs_trend(self, subsector):
        """
        Update RS trend for a subsector based on historical snapshots

        Args:
            subsector: SubSector object

        Returns:
            str: Trend ('improving', 'declining', 'stable') or None
        """
        # Get current RS value
        metrics = AlignedBreakoutSectorMetrics.query.filter_by(
            entity_type='subsector',
            subsector_id=subsector.id
        ).first()

        if not metrics or metrics.rs_vs_nifty50 is None:
            return None

        # Store current RS snapshot
        self.store_rs_history_snapshot(
            entity_type='subsector',
            entity_id=subsector.id,
            rs_value=metrics.rs_vs_nifty50,
            subsector_id=subsector.id
        )

        # Calculate trend
        trend = self.calculate_rs_trend('subsector', subsector.id, lookback_weeks=4)

        # Update metrics record
        if trend:
            metrics.rs_vs_nifty50_trend = trend
            try:
                db.session.commit()
                logger.info(f"Updated RS trend for subsector {subsector.name}: {trend}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating RS trend: {str(e)}")

        return trend

    def update_all_rs_trends(self):
        """
        Update RS trends for all stocks, sectors, and subsectors

        Returns:
            dict: Statistics about the update
        """
        from app.models import Sector, SubSector

        results = {
            'stocks': {'total': 0, 'success': 0, 'failed': 0},
            'sectors': {'total': 0, 'success': 0, 'failed': 0},
            'subsectors': {'total': 0, 'success': 0, 'failed': 0}
        }

        logger.info("Starting RS trend calculation for all entities...")

        # Update stock trends
        stocks = Instrument.query.filter_by(is_nifty500=True).all()
        results['stocks']['total'] = len(stocks)

        for stock in stocks:
            trend = self.update_stock_rs_trend(stock)
            if trend:
                results['stocks']['success'] += 1
            else:
                results['stocks']['failed'] += 1

        # Update sector trends
        sectors = Sector.query.filter_by(is_active=True).all()
        results['sectors']['total'] = len(sectors)

        for sector in sectors:
            trend = self.update_sector_rs_trend(sector)
            if trend:
                results['sectors']['success'] += 1
            else:
                results['sectors']['failed'] += 1

        # Update subsector trends
        subsectors = SubSector.query.all()
        results['subsectors']['total'] = len(subsectors)

        for subsector in subsectors:
            trend = self.update_subsector_rs_trend(subsector)
            if trend:
                results['subsectors']['success'] += 1
            else:
                results['subsectors']['failed'] += 1

        logger.info(f"RS trend calculation complete:")
        logger.info(f"  Stocks: {results['stocks']['success']}/{results['stocks']['total']}")
        logger.info(f"  Sectors: {results['sectors']['success']}/{results['sectors']['total']}")
        logger.info(f"  SubSectors: {results['subsectors']['success']}/{results['subsectors']['total']}")

        return results

    def detect_stage_transition(self, stock, new_stage):
        """
        Detect and record stage transitions for a stock

        Args:
            stock: Instrument object
            new_stage: New stage number
        """
        if not stock.current_stage or stock.current_stage == new_stage:
            return

        # Record transition
        transition = AlignedBreakoutStageTransition(
            entity_type='stock',
            instrument_id=stock.id,
            from_stage=stock.current_stage,
            to_stage=new_stage,
            transition_date=self.today,
            stage_confidence=stock.stage_confidence,
            price_at_transition=stock.last_price,
            created_at=datetime.utcnow()
        )

        db.session.add(transition)

        try:
            db.session.commit()
            logger.info(f"Recorded stage transition for {stock.tradingsymbol}: {stock.current_stage} -> {new_stage}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error recording stage transition: {str(e)}")


# Convenience function for easy import
def update_aligned_breakout_metrics(limit=None):
    """
    Update all Aligned Breakout metrics

    Args:
        limit: Optional limit on number of stocks (for testing)

    Returns:
        dict: Statistics about the update
    """
    calculator = AlignedBreakoutCalculator()
    return calculator.update_all_stock_metrics(limit=limit)
