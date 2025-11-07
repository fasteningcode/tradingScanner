"""
Stock Stage Analysis Service

This module provides functionality to perform Weinstein stage analysis on individual stocks
using historical candlestick data stored in the HistoricalData table.
"""

import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from flask import current_app
from app import db
from app.models import (
    Instrument, HistoricalData, StockStageAnalysisTask,
    Sector, SubSector
)


# Global dictionary to track running tasks (task_id -> thread)
_running_tasks = {}


def start_stock_stage_analysis(user_id: int, filter_type: str = 'nifty500',
                                sector_id: Optional[int] = None,
                                subsector_id: Optional[int] = None,
                                app=None) -> Optional[int]:
    """
    Start a new stock stage analysis task in background thread

    Args:
        user_id: User ID initiating the analysis
        filter_type: Type of filter ('nifty500', 'all', 'sector', 'subsector')
        sector_id: Sector ID for sector-specific analysis
        subsector_id: SubSector ID for subsector-specific analysis
        app: Flask app instance

    Returns:
        Task ID if started successfully, None otherwise
    """
    try:
        current_app.logger.info(
            f'Starting stock stage analysis for user {user_id}, '
            f'filter_type={filter_type}, sector_id={sector_id}, subsector_id={subsector_id}'
        )

        # Create new task
        task = StockStageAnalysisTask(
            user_id=user_id,
            filter_type=filter_type,
            sector_id=sector_id,
            subsector_id=subsector_id,
            status='pending'
        )
        db.session.add(task)
        db.session.commit()

        task_id = task.id
        current_app.logger.info(f'Created stock stage analysis task {task_id} for user {user_id}')

        # Get app context if not provided
        if app is None:
            app = current_app._get_current_object()

        # Start analysis in background thread
        thread = threading.Thread(
            target=_run_stock_stage_analysis,
            args=(task_id, app),
            daemon=True
        )
        thread.start()
        _running_tasks[task_id] = thread

        current_app.logger.info(f'Stock stage analysis task {task_id} thread started')
        return task_id

    except Exception as e:
        current_app.logger.error(f'Error starting stock stage analysis: {str(e)}', exc_info=True)
        return None


def get_stock_stage_analysis_status(user_id: int) -> Optional[Dict]:
    """
    Get status of the most recent stock stage analysis task for a user

    Args:
        user_id: User ID

    Returns:
        Task status dict or None if no task found
    """
    task = StockStageAnalysisTask.query.filter_by(user_id=user_id).order_by(
        StockStageAnalysisTask.created_at.desc()
    ).first()

    if task:
        return task.to_dict()
    return None


def cancel_stock_stage_analysis(task_id: int) -> bool:
    """
    Cancel a running stock stage analysis task

    Args:
        task_id: Task ID to cancel

    Returns:
        True if cancelled successfully, False otherwise
    """
    task = StockStageAnalysisTask.query.get(task_id)
    if not task:
        return False

    if task.status in ['completed', 'failed', 'cancelled']:
        return False

    task.status = 'cancelled'
    task.completed_at = datetime.utcnow()
    db.session.commit()

    current_app.logger.info(f'Cancelled stock stage analysis task {task_id}')
    return True


def _run_stock_stage_analysis(task_id: int, app):
    """
    Run stock stage analysis in background thread

    Args:
        task_id: Task ID
        app: Flask app instance
    """
    with app.app_context():
        try:
            current_app.logger.info(f'Stock stage analysis task {task_id}: Starting background execution')
            analyzer = StockStageAnalyzer(task_id)
            analyzer.run()
            current_app.logger.info(f'Stock stage analysis task {task_id}: Completed successfully')
        except Exception as e:
            current_app.logger.error(
                f'Stock stage analysis task {task_id} failed: {str(e)}',
                exc_info=True
            )
            try:
                task = StockStageAnalysisTask.query.get(task_id)
                if task:
                    task.status = 'failed'
                    task.error_message = str(e)
                    task.completed_at = datetime.utcnow()
                    db.session.commit()
                    current_app.logger.info(f'Stock stage analysis task {task_id}: Marked as failed in database')
            except Exception as db_error:
                current_app.logger.error(
                    f'Stock stage analysis task {task_id}: Failed to update task status: {str(db_error)}',
                    exc_info=True
                )
        finally:
            # Remove from running tasks
            if task_id in _running_tasks:
                del _running_tasks[task_id]
                current_app.logger.info(f'Stock stage analysis task {task_id}: Removed from running tasks')


class StockStageAnalyzer:
    """Handles stock-level stage analysis process"""

    def __init__(self, task_id: int):
        self.task_id = task_id
        self.task = StockStageAnalysisTask.query.get(task_id)
        if not self.task:
            raise ValueError(f'Task {task_id} not found')

    def run(self):
        """Execute the stock stage analysis"""
        current_app.logger.info(f'Stock stage analysis task {self.task_id}: Starting run()')

        # Update task status to running
        self.task.status = 'running'
        self.task.started_at = datetime.utcnow()
        db.session.commit()
        current_app.logger.info(f'Stock stage analysis task {self.task_id}: Status set to running')

        # Get stocks to analyze based on filter
        current_app.logger.info(
            f'Stock stage analysis task {self.task_id}: Getting stocks to analyze with filter_type={self.task.filter_type}'
        )
        stocks = self._get_stocks_to_analyze()
        self.task.total_stocks = len(stocks)
        db.session.commit()

        current_app.logger.info(
            f'Stock stage analysis task {self.task_id}: Found {len(stocks)} stocks to analyze'
        )

        if len(stocks) == 0:
            current_app.logger.warning(f'Stock stage analysis task {self.task_id}: No stocks found to analyze')
            self.task.status = 'completed'
            self.task.completed_at = datetime.utcnow()
            db.session.commit()
            return

        # Analyze each stock
        for stock in stocks:
            # Check if task was cancelled
            db.session.refresh(self.task)
            if self.task.status == 'cancelled':
                current_app.logger.info(f'Stock stage analysis task {self.task_id} was cancelled')
                return

            self.task.current_stock_symbol = stock.tradingsymbol
            db.session.commit()

            # Perform stage analysis on stock
            success = self._analyze_stock(stock)

            if success:
                self.task.analyzed_stocks += 1
            else:
                # Check if it was skipped due to insufficient data
                if not self._has_sufficient_data(stock.tradingsymbol):
                    self.task.skipped_stocks += 1
                else:
                    self.task.failed_stocks += 1

            # Update progress
            self.task.progress_percentage = (
                (self.task.analyzed_stocks + self.task.failed_stocks + self.task.skipped_stocks) /
                self.task.total_stocks * 100
            )
            db.session.commit()

        # Mark task as completed
        self.task.status = 'completed'
        self.task.completed_at = datetime.utcnow()
        self.task.current_stock_symbol = None
        db.session.commit()

        current_app.logger.info(
            f'Stock stage analysis task {self.task_id} completed: '
            f'Analyzed={self.task.analyzed_stocks}, '
            f'Skipped={self.task.skipped_stocks}, '
            f'Failed={self.task.failed_stocks}'
        )

    def _get_stocks_to_analyze(self) -> List[Instrument]:
        """Get list of stocks to analyze based on filter type"""
        query = Instrument.query.filter_by(
            instrument_type='EQ',
            segment='NSE'
        )

        if self.task.filter_type == 'nifty500':
            query = query.filter_by(is_nifty500=True)
        elif self.task.filter_type == 'sector' and self.task.sector_id:
            # Get all subsectors in this sector
            subsector_ids = db.session.query(SubSector.id).filter_by(
                sector_id=self.task.sector_id,
                is_active=True
            ).all()
            subsector_ids = [sid[0] for sid in subsector_ids]
            query = query.filter(Instrument.sub_sector_id.in_(subsector_ids))
        elif self.task.filter_type == 'subsector' and self.task.subsector_id:
            query = query.filter_by(sub_sector_id=self.task.subsector_id)
        # 'all' filter doesn't need additional filtering

        return query.all()

    def _has_sufficient_data(self, tradingsymbol: str) -> bool:
        """Check if stock has sufficient historical data"""
        hist_data = HistoricalData.query.filter_by(
            tradingsymbol=tradingsymbol,
            interval='day'
        ).first()

        if not hist_data:
            return False

        candles = hist_data.get_candles()
        return len(candles) >= 150

    def _analyze_stock(self, stock: Instrument) -> bool:
        """
        Perform stage analysis on a single stock

        Args:
            stock: Instrument object

        Returns:
            True if analysis succeeded, False otherwise
        """
        try:
            # Get historical data
            hist_data = HistoricalData.query.filter_by(
                tradingsymbol=stock.tradingsymbol,
                interval='day'
            ).first()

            if not hist_data:
                current_app.logger.warning(
                    f'Stock stage analysis task {self.task_id}: '
                    f'No historical data for {stock.tradingsymbol}'
                )
                return False

            # Calculate stage from candlestick data
            stage_result = self._calculate_stage_from_candles(stock.tradingsymbol, hist_data)

            if stage_result is None:
                current_app.logger.warning(
                    f'Stock stage analysis task {self.task_id}: '
                    f'Insufficient data for {stock.tradingsymbol}'
                )
                return False

            # Update stock with stage information
            stock.current_stage = stage_result['stage']
            stock.stage_confidence = stage_result['confidence']
            stock.stage_updated_at = datetime.utcnow()
            db.session.add(stock)
            db.session.commit()

            current_app.logger.debug(
                f'Stock stage analysis task {self.task_id}: '
                f'{stock.tradingsymbol} -> Stage {stage_result["stage"]} '
                f'(confidence: {stage_result["confidence"]:.1f}%)'
            )

            return True

        except Exception as e:
            current_app.logger.error(
                f'Stock stage analysis task {self.task_id}: '
                f'Error analyzing {stock.tradingsymbol}: {str(e)}'
            )
            return False

    def _calculate_stage_from_candles(self, tradingsymbol: str,
                                      hist_data: HistoricalData) -> Optional[Dict]:
        """
        Calculate Weinstein stage from candlestick data

        Args:
            tradingsymbol: Trading symbol
            hist_data: HistoricalData object containing candlestick_data JSON

        Returns:
            Dict with stage and confidence, or None if insufficient data
        """
        try:
            # Get candles from JSON data
            candles = hist_data.get_candles()

            if not candles or len(candles) < 150:
                return None

            # Extract close prices from candles
            # Candles format: [{"date": "2024-01-01", "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000}, ...]
            close_prices = [float(candle['close']) for candle in candles]

            # Calculate moving averages
            ma_30 = self._calculate_sma(close_prices, 30)
            ma_150 = self._calculate_sma(close_prices, 150)

            if ma_30 is None or ma_150 is None:
                return None

            # Get current price (latest close)
            current_price = close_prices[-1]

            # Calculate MA slopes (rate of change over last 10 days)
            ma_30_slope = self._calculate_slope(close_prices, 30, 10)
            ma_150_slope = self._calculate_slope(close_prices, 150, 10)

            # Determine stage using Weinstein methodology
            stage, confidence = self._determine_stage(
                current_price, ma_30, ma_150, ma_30_slope, ma_150_slope
            )

            return {
                'stage': stage,
                'confidence': confidence
            }

        except Exception as e:
            current_app.logger.error(
                f'Error calculating stage for {tradingsymbol}: {str(e)}'
            )
            return None

    def _calculate_sma(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period

    def _calculate_slope(self, prices: List[float], ma_period: int, slope_period: int) -> float:
        """
        Calculate slope of moving average over recent period

        Returns:
            Positive for uptrend, negative for downtrend, near 0 for flat
        """
        if len(prices) < ma_period + slope_period:
            return 0.0

        # Calculate MAs for the slope period
        mas = []
        for i in range(slope_period):
            idx = len(prices) - slope_period + i
            if idx >= ma_period - 1:
                ma = sum(prices[idx - ma_period + 1:idx + 1]) / ma_period
                mas.append(ma)

        if len(mas) < 2:
            return 0.0

        # Simple linear regression slope
        n = len(mas)
        sum_xy = sum((i * mas[i]) for i in range(n))
        sum_x = sum(range(n))
        sum_y = sum(mas)
        sum_x2 = sum(i * i for i in range(n))

        if n * sum_x2 - sum_x * sum_x == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

        # Normalize slope as percentage
        avg_price = sum(mas) / len(mas)
        if avg_price > 0:
            slope_pct = (slope / avg_price) * 100
        else:
            slope_pct = 0.0

        return slope_pct

    def _determine_stage(self, price: float, ma_30: float, ma_150: float,
                        ma_30_slope: float, ma_150_slope: float) -> tuple:
        """
        Determine Weinstein stage based on price and moving averages

        Returns:
            Tuple of (stage, confidence)
        """
        # Threshold for "flat" slope (in percentage)
        FLAT_THRESHOLD = 0.1

        # Stage 2: Markup (Bullish trend)
        # - Price > MA30 > MA150
        # - Both MAs rising
        # - 30-day MA rising faster than 150-day MA
        if (price > ma_30 > ma_150 and
            ma_30_slope > FLAT_THRESHOLD and
            ma_150_slope > -FLAT_THRESHOLD):

            # Higher confidence if both MAs strongly rising
            if ma_30_slope > 0.5 and ma_150_slope > 0.2:
                confidence = 90.0
            elif ma_30_slope > 0.3:
                confidence = 75.0
            else:
                confidence = 60.0

            return (2, confidence)

        # Stage 4: Decline (Bearish trend)
        # - Price < MA30 < MA150
        # - Both MAs falling
        # - 30-day MA falling faster than 150-day MA
        if (price < ma_30 < ma_150 and
            ma_30_slope < -FLAT_THRESHOLD and
            ma_150_slope < FLAT_THRESHOLD):

            # Higher confidence if both MAs strongly falling
            if ma_30_slope < -0.5 and ma_150_slope < -0.2:
                confidence = 90.0
            elif ma_30_slope < -0.3:
                confidence = 75.0
            else:
                confidence = 60.0

            return (4, confidence)

        # Stage 1: Accumulation (Basing)
        # - Price near or below MAs
        # - MAs flattening or 30-day starting to turn up
        # - Coming out of Stage 4
        if (price <= ma_30 and
            abs(ma_30_slope) < 0.3 and
            abs(ma_150_slope) < 0.3):

            # Higher confidence if 30-day MA turning up
            if ma_30_slope > 0 and ma_150_slope >= -FLAT_THRESHOLD:
                confidence = 70.0
            else:
                confidence = 55.0

            return (1, confidence)

        # Stage 3: Distribution (Topping)
        # - Price near or above MAs
        # - MAs flattening or 30-day starting to turn down
        # - Coming out of Stage 2
        if (price >= ma_30 and
            abs(ma_30_slope) < 0.3 and
            abs(ma_150_slope) < 0.3):

            # Higher confidence if 30-day MA turning down
            if ma_30_slope < 0 and ma_150_slope <= FLAT_THRESHOLD:
                confidence = 70.0
            else:
                confidence = 55.0

            return (3, confidence)

        # Default: Use price vs MA position to determine stage
        if price > ma_30 and price > ma_150:
            # Above both MAs - likely Stage 2 or 3
            if ma_30 > ma_150:
                return (2, 50.0)  # Stage 2 with low confidence
            else:
                return (3, 50.0)  # Stage 3 with low confidence
        else:
            # Below MAs - likely Stage 4 or 1
            if ma_30 < ma_150:
                return (4, 50.0)  # Stage 4 with low confidence
            else:
                return (1, 50.0)  # Stage 1 with low confidence
