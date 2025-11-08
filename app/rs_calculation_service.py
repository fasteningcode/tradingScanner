"""
Relative Strength (RS) Calculation Service

This service calculates the Relative Strength of stocks relative to their
subsector and sector indices based on a user-specified base date.

RS Formula:
    RS = (Stock % Change) / (Index % Change)

Where:
    Stock % Change = ((Current Price - Base Price) / Base Price) × 100
    Index % Change = ((Current Index - Base Index) / Base Index) × 100

Interpretation:
    RS > 1.0: Stock outperformed the index
    RS < 1.0: Stock underperformed the index
    RS = 1.0: Stock performed equally with the index

Example:
    If stock gained 20% and sector gained 15%:
    RS = 20% / 15% = 1.33
    This means the stock outperformed by a factor of 1.33
"""

import threading
import json
from datetime import datetime, date
from typing import Optional, Dict
from flask import current_app
from app import db
from app.models import RSCalculationTask, Instrument, HistoricalData, IndexHistory


# Dictionary to track running tasks {task_id: thread}
_running_tasks = {}


def start_rs_calculation(user_id: int, base_date: date, app=None) -> Optional[int]:
    """
    Start RS calculation for all stocks in the background

    Args:
        user_id: User ID
        base_date: Base date for RS calculation (e.g., date(2024, 7, 1))
        app: Flask app instance

    Returns:
        Task ID if started successfully, None otherwise
    """
    try:
        current_app.logger.info(
            f'Starting RS calculation for user {user_id}, base_date={base_date}'
        )

        # Create new task
        task = RSCalculationTask(
            user_id=user_id,
            base_date=base_date,
            status='pending'
        )
        db.session.add(task)
        db.session.commit()

        task_id = task.id
        current_app.logger.info(f'Created RS calculation task {task_id} for user {user_id}')

        # Get app context if not provided
        if app is None:
            app = current_app._get_current_object()

        # Start calculation in background thread
        thread = threading.Thread(
            target=_run_rs_calculation,
            args=(task_id, app),
            daemon=True
        )
        thread.start()
        _running_tasks[task_id] = thread

        current_app.logger.info(f'RS calculation task {task_id} thread started')
        return task_id

    except Exception as e:
        current_app.logger.error(f'Error starting RS calculation: {str(e)}', exc_info=True)
        return None


def get_rs_calculation_status(user_id: int) -> Optional[Dict]:
    """
    Get status of the most recent RS calculation task for a user

    Args:
        user_id: User ID

    Returns:
        Task status dictionary or None if no task found
    """
    try:
        task = RSCalculationTask.query.filter_by(user_id=user_id).order_by(
            RSCalculationTask.created_at.desc()
        ).first()

        if task:
            return task.to_dict()
        return None

    except Exception as e:
        current_app.logger.error(f'Error getting RS calculation status: {str(e)}', exc_info=True)
        return None


def cancel_rs_calculation(task_id: int) -> bool:
    """
    Cancel a running RS calculation task

    Args:
        task_id: Task ID

    Returns:
        True if cancelled successfully, False otherwise
    """
    try:
        task = RSCalculationTask.query.get(task_id)
        if task and task.status == 'running':
            task.status = 'cancelled'
            task.completed_at = datetime.utcnow()
            db.session.commit()
            current_app.logger.info(f'RS calculation task {task_id} cancelled')
            return True
        return False

    except Exception as e:
        current_app.logger.error(f'Error cancelling RS calculation: {str(e)}', exc_info=True)
        return False


def _run_rs_calculation(task_id: int, app):
    """
    Run RS calculation in background thread

    Args:
        task_id: Task ID
        app: Flask app instance
    """
    with app.app_context():
        try:
            current_app.logger.info(f'RS calculation task {task_id}: Starting background execution')
            calculator = RSCalculator(task_id)
            calculator.run()
            current_app.logger.info(f'RS calculation task {task_id}: Completed successfully')
        except Exception as e:
            current_app.logger.error(
                f'RS calculation task {task_id} failed: {str(e)}',
                exc_info=True
            )
            try:
                task = RSCalculationTask.query.get(task_id)
                if task:
                    task.status = 'failed'
                    task.error_message = str(e)
                    task.completed_at = datetime.utcnow()
                    db.session.commit()
                    current_app.logger.info(f'RS calculation task {task_id}: Marked as failed in database')
            except Exception as db_error:
                current_app.logger.error(
                    f'RS calculation task {task_id}: Failed to update task status: {str(db_error)}',
                    exc_info=True
                )
        finally:
            # Remove from running tasks
            if task_id in _running_tasks:
                del _running_tasks[task_id]
                current_app.logger.info(f'RS calculation task {task_id}: Removed from running tasks')


class RSCalculator:
    """Handles RS calculation process"""

    def __init__(self, task_id: int):
        self.task_id = task_id
        self.task = RSCalculationTask.query.get(task_id)
        if not self.task:
            raise ValueError(f'Task {task_id} not found')

    def run(self):
        """Execute the RS calculation"""
        current_app.logger.info(f'RS calculation task {self.task_id}: Starting run()')

        # Update task status to running
        self.task.status = 'running'
        self.task.started_at = datetime.utcnow()
        db.session.commit()
        current_app.logger.info(f'RS calculation task {self.task_id}: Status set to running')

        # Get all NIFTY 500 stocks with subsector assignment
        current_app.logger.info(f'RS calculation task {self.task_id}: Fetching stocks to process')
        stocks = Instrument.query.filter_by(
            exchange='NSE',
            instrument_type='EQ',
            is_nifty500=True
        ).filter(
            Instrument.sub_sector_id.isnot(None)  # Only stocks with subsector assignment
        ).all()

        self.task.total_stocks = len(stocks)
        db.session.commit()

        current_app.logger.info(
            f'RS calculation task {self.task_id}: Found {len(stocks)} stocks to process'
        )

        if len(stocks) == 0:
            current_app.logger.warning(f'RS calculation task {self.task_id}: No stocks found to process')
            self.task.status = 'completed'
            self.task.completed_at = datetime.utcnow()
            db.session.commit()
            return

        # Process each stock
        for stock in stocks:
            # Check if task was cancelled
            db.session.refresh(self.task)
            if self.task.status == 'cancelled':
                current_app.logger.info(f'RS calculation task {self.task_id} was cancelled')
                return

            try:
                self.task.current_stock_symbol = stock.tradingsymbol
                db.session.commit()

                current_app.logger.debug(
                    f'RS calculation task {self.task_id}: Processing {stock.tradingsymbol}'
                )

                # Calculate RS for this stock
                rs_result = self._calculate_rs_for_stock(stock)

                if rs_result:
                    # Update stock with RS values
                    stock.rs_vs_subsector = rs_result['rs_vs_subsector']
                    stock.rs_vs_sector = rs_result['rs_vs_sector']
                    stock.rs_base_date = self.task.base_date
                    stock.rs_updated_at = datetime.utcnow()
                    db.session.add(stock)

                    current_app.logger.info(
                        f'RS calculation task {self.task_id}: {stock.tradingsymbol} - '
                        f'RS_SUB={rs_result["rs_vs_subsector"]:.2f}, '
                        f'RS_SEC={rs_result["rs_vs_sector"]:.2f}'
                    )

                    self.task.processed_stocks += 1
                else:
                    current_app.logger.warning(
                        f'RS calculation task {self.task_id}: Skipping {stock.tradingsymbol} - '
                        f'insufficient data'
                    )
                    self.task.skipped_stocks += 1

                # Update progress
                self.task.progress_percentage = (self.task.processed_stocks / self.task.total_stocks) * 100
                db.session.commit()

            except Exception as e:
                self.task.failed_stocks += 1
                error_msg = f'Error processing {stock.tradingsymbol}: {str(e)}'
                current_app.logger.error(
                    f'RS calculation task {self.task_id}: {error_msg}',
                    exc_info=True
                )
                db.session.commit()

        # Mark task as completed
        self.task.status = 'completed'
        self.task.completed_at = datetime.utcnow()
        self.task.current_stock_symbol = None
        db.session.commit()

        current_app.logger.info(
            f'RS calculation task {self.task_id}: Completed - '
            f'Processed: {self.task.processed_stocks}, '
            f'Skipped: {self.task.skipped_stocks}, '
            f'Failed: {self.task.failed_stocks}'
        )

    def _calculate_rs_for_stock(self, stock: Instrument) -> Optional[Dict]:
        """
        Calculate RS for a single stock

        Args:
            stock: Instrument object

        Returns:
            Dictionary with rs_vs_subsector and rs_vs_sector, or None if insufficient data
        """
        try:
            # Get subsector and sector info
            if not stock.sub_sector_obj:
                current_app.logger.warning(
                    f'RS calculation task {self.task_id}: {stock.tradingsymbol} has no subsector'
                )
                return None

            subsector = stock.sub_sector_obj
            sector = subsector.sector

            if not subsector or not sector:
                current_app.logger.warning(
                    f'RS calculation task {self.task_id}: {stock.tradingsymbol} - '
                    f'Missing subsector or sector relationship'
                )
                return None

            # Get stock prices at base date and current
            stock_base_price = self._get_stock_price(stock.tradingsymbol, self.task.base_date)
            stock_current_price = self._get_stock_price(stock.tradingsymbol, None)  # Latest

            if not stock_base_price or not stock_current_price:
                current_app.logger.warning(
                    f'RS calculation task {self.task_id}: {stock.tradingsymbol} - '
                    f'Missing stock price data (base={stock_base_price}, current={stock_current_price})'
                )
                return None

            # Get subsector index at base date and current
            subsector_base_index = self._get_index_value(subsector.index_symbol, self.task.base_date)
            subsector_current_index = self._get_index_value(subsector.index_symbol, None)  # Latest

            if not subsector_base_index or not subsector_current_index:
                current_app.logger.warning(
                    f'RS calculation task {self.task_id}: {stock.tradingsymbol} - '
                    f'Missing subsector index data (base={subsector_base_index}, current={subsector_current_index})'
                )
                return None

            # Get sector index at base date and current
            sector_base_index = self._get_index_value(sector.index_symbol, self.task.base_date)
            sector_current_index = self._get_index_value(sector.index_symbol, None)  # Latest

            if not sector_base_index or not sector_current_index:
                current_app.logger.warning(
                    f'RS calculation task {self.task_id}: {stock.tradingsymbol} - '
                    f'Missing sector index data (base={sector_base_index}, current={sector_current_index})'
                )
                return None

            # Calculate percentage changes
            stock_pct_change = ((stock_current_price - stock_base_price) / stock_base_price) * 100
            subsector_pct_change = ((subsector_current_index - subsector_base_index) / subsector_base_index) * 100
            sector_pct_change = ((sector_current_index - sector_base_index) / sector_base_index) * 100

            # Calculate RS values
            # RS = (Stock % Change) / (Index % Change)
            # RS > 1.0 means stock outperformed the index
            # RS < 1.0 means stock underperformed the index
            # Note: If index % change is zero, RS is undefined - we'll skip those cases
            if subsector_pct_change == 0 or sector_pct_change == 0:
                current_app.logger.warning(
                    f'RS calculation task {self.task_id}: {stock.tradingsymbol} - '
                    f'Index percentage change is zero'
                )
                return None

            rs_vs_subsector = stock_pct_change / subsector_pct_change
            rs_vs_sector = stock_pct_change / sector_pct_change

            current_app.logger.debug(
                f'RS calculation task {self.task_id}: {stock.tradingsymbol} - '
                f'Stock: {stock_base_price:.2f} -> {stock_current_price:.2f} ({stock_pct_change:+.2f}%), '
                f'SubSec: {subsector_base_index:.2f} -> {subsector_current_index:.2f} ({subsector_pct_change:+.2f}%), '
                f'Sector: {sector_base_index:.2f} -> {sector_current_index:.2f} ({sector_pct_change:+.2f}%)'
            )

            return {
                'rs_vs_subsector': round(rs_vs_subsector, 2),
                'rs_vs_sector': round(rs_vs_sector, 2)
            }

        except Exception as e:
            current_app.logger.error(
                f'RS calculation task {self.task_id}: Error calculating RS for {stock.tradingsymbol}: {str(e)}',
                exc_info=True
            )
            return None

    def _get_stock_price(self, tradingsymbol: str, target_date: Optional[date]) -> Optional[float]:
        """
        Get stock price for a specific date or latest

        Args:
            tradingsymbol: Trading symbol
            target_date: Target date, or None for latest

        Returns:
            Close price or None if not found
        """
        try:
            # Get historical data record
            hist_data = HistoricalData.query.filter_by(
                tradingsymbol=tradingsymbol,
                interval='day'
            ).first()

            if not hist_data:
                return None

            # Parse candles
            candles = hist_data.get_candles()
            if not candles or len(candles) == 0:
                return None

            # If no target date, return latest price
            if target_date is None:
                latest_candle = candles[-1]
                return float(latest_candle.get('close', 0))

            # Find candle for target date
            target_date_str = target_date.isoformat()
            for candle in candles:
                candle_date_str = candle.get('date', '')
                # Normalize date format (remove time part if present)
                if 'T' in candle_date_str:
                    candle_date_str = candle_date_str.split('T')[0]

                if candle_date_str == target_date_str:
                    return float(candle.get('close', 0))

            # If exact date not found, try to find closest earlier date
            for candle in reversed(candles):
                candle_date_str = candle.get('date', '')
                if 'T' in candle_date_str:
                    candle_date_str = candle_date_str.split('T')[0]

                if candle_date_str <= target_date_str:
                    current_app.logger.debug(
                        f'RS calculation task {self.task_id}: Using closest date {candle_date_str} '
                        f'for target {target_date_str} for {tradingsymbol}'
                    )
                    return float(candle.get('close', 0))

            return None

        except Exception as e:
            current_app.logger.error(
                f'RS calculation task {self.task_id}: Error getting price for {tradingsymbol}: {str(e)}',
                exc_info=True
            )
            return None

    def _get_index_value(self, index_symbol: str, target_date: Optional[date]) -> Optional[float]:
        """
        Get index value for a specific date or latest

        Args:
            index_symbol: Index symbol
            target_date: Target date, or None for latest

        Returns:
            Index value or None if not found
        """
        try:
            query = IndexHistory.query.filter_by(index_symbol=index_symbol)

            if target_date:
                # Try exact match first
                record = query.filter(IndexHistory.date == target_date).first()

                if not record:
                    # Try closest earlier date
                    record = query.filter(
                        IndexHistory.date <= target_date
                    ).order_by(IndexHistory.date.desc()).first()

                    if record:
                        current_app.logger.debug(
                            f'RS calculation task {self.task_id}: Using closest date {record.date} '
                            f'for target {target_date} for index {index_symbol}'
                        )
            else:
                # Get latest
                record = query.order_by(IndexHistory.date.desc()).first()

            if record:
                return record.index_value

            return None

        except Exception as e:
            current_app.logger.error(
                f'RS calculation task {self.task_id}: Error getting index value for {index_symbol}: {str(e)}',
                exc_info=True
            )
            return None
