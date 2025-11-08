"""
Volume Dry-Up Analysis Service
Implements institutional-grade volume dry-up scanner with background task execution
"""
import json
import threading
from datetime import datetime
from typing import Optional, Dict, List
from flask import current_app
from app import db
from app.models import VolumeDryUpTask, Instrument, HistoricalData

# Global dictionary to track running tasks
_running_tasks = {}


def start_volume_dryup_analysis(user_id: int, min_volume_pct: float = 50.0,
                                 max_consolidation_pct: float = 6.0, app=None) -> Optional[int]:
    """
    Start volume dry-up analysis in background thread

    Args:
        user_id: User ID initiating the analysis
        min_volume_pct: Maximum allowed volume as % of 20-day average (default 50%)
        max_consolidation_pct: Maximum allowed 5-day consolidation range (default 6%)
        app: Flask app instance

    Returns:
        Task ID if started successfully, None otherwise
    """
    try:
        # Create new task
        task = VolumeDryUpTask(
            user_id=user_id,
            min_volume_pct=min_volume_pct,
            max_consolidation_pct=max_consolidation_pct,
            status='pending',
            progress_percentage=0.0,
            total_stocks=0,
            analyzed_stocks=0,
            qualified_stocks=0,
            failed_stocks=0
        )

        db.session.add(task)
        db.session.commit()

        task_id = task.id
        current_app.logger.info(f'Created volume dry-up task {task_id} for user {user_id}')

        # Get app context
        if app is None:
            app = current_app._get_current_object()

        # Start background thread
        thread = threading.Thread(
            target=_run_volume_dryup_analysis,
            args=(task_id, app),
            daemon=True
        )
        thread.start()
        _running_tasks[task_id] = thread

        current_app.logger.info(f'Started volume dry-up analysis thread for task {task_id}')
        return task_id

    except Exception as e:
        current_app.logger.error(f'Error starting volume dry-up analysis: {str(e)}', exc_info=True)
        db.session.rollback()
        return None


def get_volume_dryup_status(user_id: int) -> Optional[Dict]:
    """
    Get status of most recent volume dry-up task for a user

    Args:
        user_id: User ID

    Returns:
        Dictionary with task status or None if no task found
    """
    task = VolumeDryUpTask.query.filter_by(user_id=user_id).order_by(
        VolumeDryUpTask.created_at.desc()
    ).first()

    if task:
        return task.to_dict()
    return None


def cancel_volume_dryup_analysis(task_id: int) -> bool:
    """
    Cancel a running volume dry-up analysis task

    Args:
        task_id: Task ID to cancel

    Returns:
        True if cancelled successfully, False otherwise
    """
    try:
        task = VolumeDryUpTask.query.get(task_id)
        if task and task.status == 'running':
            task.status = 'cancelled'
            task.completed_at = datetime.utcnow()
            task.current_stock_symbol = None
            db.session.commit()
            current_app.logger.info(f'Cancelled volume dry-up task {task_id}')
            return True
        return False
    except Exception as e:
        current_app.logger.error(f'Error cancelling task {task_id}: {str(e)}', exc_info=True)
        db.session.rollback()
        return False


def get_qualified_stocks(user_id: int, filters: Dict = None) -> List[Dict]:
    """
    Get list of stocks that qualified in the last analysis

    Args:
        user_id: User ID
        filters: Optional filters (stage, classification, etc.)

    Returns:
        List of qualified stocks with their metrics
    """
    try:
        query = Instrument.query.filter_by(volume_dryup_status='qualified')

        # Apply filters
        if filters:
            if filters.get('stage'):
                query = query.filter_by(current_stage=filters['stage'])

            if filters.get('classification'):
                query = query.filter_by(volume_dryup_classification=filters['classification'])

            if filters.get('max_distance_from_high'):
                # Calculate distance (need price and 52w high data)
                pass

        stocks = query.order_by(Instrument.volume_ratio_pct.asc()).all()

        results = []
        for stock in stocks:
            results.append({
                'symbol': stock.tradingsymbol,
                'name': stock.name,
                'current_stage': stock.current_stage,
                'volume_ratio_pct': round(stock.volume_ratio_pct, 1) if stock.volume_ratio_pct else None,
                'consolidation_5d_pct': round(stock.consolidation_5d_pct, 2) if stock.consolidation_5d_pct else None,
                'classification': stock.volume_dryup_classification,
                'declining_days': stock.volume_declining_days,
                'last_price': stock.last_price,
                'updated_at': stock.volume_dryup_updated_at.isoformat() if stock.volume_dryup_updated_at else None
            })

        return results

    except Exception as e:
        current_app.logger.error(f'Error getting qualified stocks: {str(e)}', exc_info=True)
        return []


def _run_volume_dryup_analysis(task_id: int, app):
    """
    Background thread function to run volume dry-up analysis

    Args:
        task_id: Task ID to process
        app: Flask app instance
    """
    with app.app_context():
        try:
            analyzer = VolumeDryUpAnalyzer(task_id)
            analyzer.run()
        except Exception as e:
            current_app.logger.error(f'Volume dry-up task {task_id} failed: {str(e)}', exc_info=True)
            task = VolumeDryUpTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                task.current_stock_symbol = None
                db.session.commit()
        finally:
            if task_id in _running_tasks:
                del _running_tasks[task_id]


class VolumeDryUpAnalyzer:
    """
    Volume Dry-Up Analyzer
    Implements the strict institutional-grade algorithm with 2 criteria:
    1. Volume < X% of 20-day average (default 50%)
    2. Price consolidation < Y% over 5 days (default 6%)
    """

    def __init__(self, task_id: int):
        """Initialize analyzer with task ID"""
        self.task_id = task_id
        self.task = VolumeDryUpTask.query.get(task_id)

        if not self.task:
            raise ValueError(f'Task {task_id} not found')

        current_app.logger.info(f'Initialized VolumeDryUpAnalyzer for task {task_id}')

    def run(self):
        """Execute the volume dry-up analysis"""
        current_app.logger.info(f'Starting volume dry-up analysis for task {self.task_id}')

        # Update status to running
        self.task.status = 'running'
        self.task.started_at = datetime.utcnow()
        db.session.commit()

        # Get all stocks with historical data
        stocks_with_data = HistoricalData.query.filter_by(interval='day').all()

        self.task.total_stocks = len(stocks_with_data)
        db.session.commit()

        current_app.logger.info(f'Task {self.task_id}: Processing {self.task.total_stocks} stocks')

        # Process each stock
        for hist_data in stocks_with_data:
            # Check for cancellation
            db.session.refresh(self.task)
            if self.task.status == 'cancelled':
                current_app.logger.info(f'Task {self.task_id} cancelled by user')
                return

            # Update current stock
            self.task.current_stock_symbol = hist_data.tradingsymbol
            db.session.commit()

            # Analyze stock
            try:
                self._analyze_stock(hist_data)
                self.task.analyzed_stocks += 1
            except Exception as e:
                current_app.logger.error(
                    f'Task {self.task_id}: Error analyzing {hist_data.tradingsymbol}: {str(e)}'
                )
                self.task.failed_stocks += 1

            # Update progress
            self.task.progress_percentage = (self.task.analyzed_stocks / self.task.total_stocks) * 100
            db.session.commit()

        # Mark as completed
        self.task.status = 'completed'
        self.task.completed_at = datetime.utcnow()
        self.task.current_stock_symbol = None
        db.session.commit()

        current_app.logger.info(
            f'Task {self.task_id} completed: {self.task.qualified_stocks} qualified, '
            f'{self.task.failed_stocks} failed out of {self.task.total_stocks} stocks'
        )

    def _analyze_stock(self, hist_data: HistoricalData):
        """
        Analyze a single stock for volume dry-up pattern

        Args:
            hist_data: HistoricalData record for the stock
        """
        # Get instrument record
        instrument = Instrument.query.filter_by(tradingsymbol=hist_data.tradingsymbol).first()
        if not instrument:
            return

        # Parse candlestick data
        try:
            candles = json.loads(hist_data.candlestick_data)
        except (json.JSONDecodeError, TypeError):
            return

        # Need at least 20 days for volume analysis
        if len(candles) < 20:
            instrument.volume_dryup_status = 'not_qualified'
            instrument.volume_dryup_updated_at = datetime.utcnow()
            db.session.commit()
            return

        # CRITERION 1: Volume Dry-Up
        volume_ratio = self._calculate_volume_ratio(candles)
        if volume_ratio is None or volume_ratio >= self.task.min_volume_pct:
            instrument.volume_dryup_status = 'not_qualified'
            instrument.volume_ratio_pct = volume_ratio
            instrument.volume_dryup_updated_at = datetime.utcnow()
            db.session.commit()
            return

        # CRITERION 2: Price Consolidation
        consolidation_range = self._calculate_consolidation_range(candles)
        if consolidation_range is None or consolidation_range >= self.task.max_consolidation_pct:
            instrument.volume_dryup_status = 'not_qualified'
            instrument.volume_ratio_pct = volume_ratio
            instrument.consolidation_5d_pct = consolidation_range
            instrument.volume_dryup_updated_at = datetime.utcnow()
            db.session.commit()
            return

        # QUALIFIED! Get additional metrics
        declining_days = self._count_declining_volume_days(candles)
        classification = self._classify_dryup(volume_ratio, consolidation_range)

        # Update instrument with results
        instrument.volume_dryup_status = 'qualified'
        instrument.volume_ratio_pct = volume_ratio
        instrument.consolidation_5d_pct = consolidation_range
        instrument.volume_dryup_classification = classification
        instrument.volume_declining_days = declining_days
        instrument.volume_dryup_updated_at = datetime.utcnow()

        db.session.commit()

        # Increment qualified count
        self.task.qualified_stocks += 1

        current_app.logger.debug(
            f'Task {self.task_id}: {hist_data.tradingsymbol} QUALIFIED - '
            f'Vol: {volume_ratio:.1f}%, Consol: {consolidation_range:.2f}%, Class: {classification}'
        )

    def _calculate_volume_ratio(self, candles: List[Dict]) -> Optional[float]:
        """
        Calculate current volume as percentage of 20-day average

        Returns:
            Volume ratio percentage or None if insufficient data
        """
        if len(candles) < 20:
            return None

        # Get last 20 days volumes
        volumes_20d = [c.get('volume', 0) for c in candles[-20:]]
        avg_volume_20d = sum(volumes_20d) / 20

        if avg_volume_20d == 0:
            return None

        current_volume = candles[-1].get('volume', 0)
        return (current_volume / avg_volume_20d) * 100

    def _calculate_consolidation_range(self, candles: List[Dict]) -> Optional[float]:
        """
        Calculate price consolidation range over last 5 days as percentage

        Returns:
            Consolidation range percentage or None if insufficient data
        """
        if len(candles) < 5:
            return None

        # Get last 5 days
        last_5 = candles[-5:]

        highs = [c.get('high', 0) for c in last_5]
        lows = [c.get('low', 0) for c in last_5]

        max_high = max(highs)
        min_low = min(lows)

        if min_low == 0:
            return None

        return ((max_high - min_low) / min_low) * 100

    def _count_declining_volume_days(self, candles: List[Dict]) -> int:
        """
        Count how many of the last 10 days had declining volume

        Returns:
            Count of declining volume days (out of 9 comparisons)
        """
        if len(candles) < 10:
            return 0

        last_10_volumes = [c.get('volume', 0) for c in candles[-10:]]

        declining_count = 0
        for i in range(1, len(last_10_volumes)):
            if last_10_volumes[i] < last_10_volumes[i-1]:
                declining_count += 1

        return declining_count

    def _classify_dryup(self, volume_ratio: float, consolidation_range: float) -> str:
        """
        Classify the dry-up pattern based on strength

        Args:
            volume_ratio: Volume as % of 20-day average
            consolidation_range: 5-day consolidation range %

        Returns:
            Classification: 'extreme', 'strong', 'good', or 'moderate'
        """
        if volume_ratio < 30 and consolidation_range < 3:
            return 'extreme'
        elif volume_ratio < 35 and consolidation_range < 4:
            return 'strong'
        elif volume_ratio < 40:
            return 'good'
        else:
            return 'moderate'
