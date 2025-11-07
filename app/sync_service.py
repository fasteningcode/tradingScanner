"""
Historical Data Sync Service

This module handles syncing the latest candlestick data from Kite Connect API
to update existing historical data without duplicates.
"""

import time
import threading
from datetime import datetime, timedelta, date
from typing import Optional, Tuple
from flask import current_app
from app import db
from app.models import Instrument, HistoricalData, HistoricalDataSettings, User, SyncTask
from app.kite_auth import get_kite_client


# Global dictionary to store active sync threads
active_syncs = {}


def start_sync_task(user_id: int, app) -> Tuple[bool, str, Optional[int]]:
    """
    Start a new sync task for the user

    Args:
        user_id: ID of the user
        app: Flask app instance

    Returns:
        Tuple of (success, message, task_id)
    """
    try:
        # Check if there's already an active sync task
        existing_task = SyncTask.query.filter_by(
            user_id=user_id,
            status='running'
        ).first()

        if existing_task:
            return False, 'A sync task is already running', None

        # Get user's historical data settings
        settings = HistoricalDataSettings.query.filter_by(user_id=user_id).first()
        if not settings:
            return False, 'Please configure historical data settings first', None

        # Count stocks with existing data
        stocks_count = HistoricalData.query.filter_by(
            interval=settings.candle_interval
        ).count()

        if stocks_count == 0:
            return False, 'No historical data found. Please download historical data first.', None

        # Create new sync task
        task = SyncTask(
            user_id=user_id,
            interval=settings.candle_interval,
            total_stocks=stocks_count,
            status='pending'
        )
        db.session.add(task)
        db.session.commit()

        # Start sync in background thread
        syncer = HistoricalDataSyncer(task.id, app)
        syncer.start_sync()

        current_app.logger.info(f'Started sync task {task.id} for user {user_id}')

        return True, 'Sync task started successfully', task.id

    except Exception as e:
        current_app.logger.error(f'Error starting sync task: {str(e)}')
        return False, str(e), None


def get_sync_status(user_id: int) -> Optional[dict]:
    """
    Get the status of the current sync task for a user

    Args:
        user_id: ID of the user

    Returns:
        Dictionary with sync status or None
    """
    try:
        task = SyncTask.query.filter_by(user_id=user_id).order_by(
            SyncTask.created_at.desc()
        ).first()

        if not task:
            return None

        return task.to_dict()

    except Exception as e:
        current_app.logger.error(f'Error getting sync status: {str(e)}')
        return None


def cancel_sync_task(task_id: int) -> Tuple[bool, str]:
    """
    Cancel a running sync task

    Args:
        task_id: ID of the sync task

    Returns:
        Tuple of (success, message)
    """
    try:
        task = SyncTask.query.get(task_id)
        if not task:
            return False, 'Task not found'

        if task.status != 'running':
            return False, f'Task is not running (status: {task.status})'

        # Stop the sync
        if task_id in active_syncs:
            syncer = active_syncs[task_id]
            syncer.cancel_sync()

        task.status = 'cancelled'
        task.completed_at = datetime.utcnow()
        db.session.commit()

        return True, 'Sync task cancelled successfully'

    except Exception as e:
        current_app.logger.error(f'Error cancelling sync task: {str(e)}')
        return False, str(e)


class HistoricalDataSyncer:
    """Service class to handle syncing latest historical data"""

    def __init__(self, task_id: int, app):
        """
        Initialize syncer with a task ID

        Args:
            task_id: ID of the SyncTask to process
            app: Flask app instance
        """
        self.task_id = task_id
        self.task = None
        self.user = None
        self.kite = None
        self.should_stop = False
        self.app = app

    def start_sync(self):
        """Start the sync process in a background thread"""
        # Start sync in background thread
        thread = threading.Thread(
            target=self._sync_worker,
            daemon=True,
            name=f"SyncWorker-{self.task_id}"
        )
        active_syncs[self.task_id] = self
        thread.start()

        self.app.logger.info(f"Started sync task {self.task_id} in background thread")

    def cancel_sync(self):
        """Cancel the running sync"""
        self.should_stop = True
        self.app.logger.info(f"Cancelled sync task {self.task_id}")

    def _sync_worker(self):
        """Main worker function that runs in background thread"""
        with self.app.app_context():
            try:
                current_app.logger.info(f"Sync task {self.task_id}: Worker thread started")

                # Load task and user
                self.task = SyncTask.query.get(self.task_id)
                if not self.task:
                    current_app.logger.error(f"Sync task {self.task_id} not found")
                    return

                self.user = User.query.get(self.task.user_id)
                if not self.user or not self.user.kite_access_token:
                    error_msg = 'User not found or Kite access token not available'
                    current_app.logger.error(f"Sync task {self.task_id}: {error_msg}")
                    self.task.status = 'failed'
                    self.task.error_message = error_msg
                    db.session.commit()
                    return

                # Initialize Kite client
                try:
                    self.kite = get_kite_client(access_token=self.user.kite_access_token)
                    current_app.logger.info(f"Sync task {self.task_id}: Kite client initialized")
                except Exception as e:
                    error_msg = f'Failed to initialize Kite client: {str(e)}'
                    current_app.logger.error(f"Sync task {self.task_id}: {error_msg}")
                    self.task.status = 'failed'
                    self.task.error_message = error_msg
                    db.session.commit()
                    return

                # Update task status to running
                self.task.status = 'running'
                self.task.started_at = datetime.utcnow()
                db.session.commit()

                # Get user's settings
                settings = HistoricalDataSettings.query.filter_by(
                    user_id=self.user.id
                ).first()

                if not settings:
                    error_msg = 'Historical data settings not found'
                    current_app.logger.error(f"Sync task {self.task_id}: {error_msg}")
                    self.task.status = 'failed'
                    self.task.error_message = error_msg
                    db.session.commit()
                    return

                # Get all stocks with existing historical data
                existing_data = HistoricalData.query.filter_by(
                    interval=self.task.interval
                ).all()

                current_app.logger.info(
                    f"Sync task {self.task_id}: Found {len(existing_data)} stocks with existing data"
                )

                # Sync each stock
                rate_limit_delay = 1.0 / settings.requests_per_second

                for hist_data in existing_data:
                    if self.should_stop:
                        current_app.logger.info(f"Sync task {self.task_id}: Stopped by user")
                        break

                    try:
                        self._sync_stock(hist_data, settings)
                        self.task.synced_stocks += 1
                        db.session.commit()

                        current_app.logger.info(
                            f"Sync task {self.task_id}: Synced {hist_data.tradingsymbol} "
                            f"({self.task.synced_stocks}/{self.task.total_stocks})"
                        )

                    except Exception as e:
                        self.task.failed_stocks += 1
                        error_msg = f"Error syncing {hist_data.tradingsymbol}: {str(e)}"
                        current_app.logger.error(f"Sync task {self.task_id}: {error_msg}")
                        db.session.commit()

                    # Rate limiting
                    time.sleep(rate_limit_delay)

                # Mark task as completed
                self.task.status = 'completed'
                self.task.completed_at = datetime.utcnow()
                db.session.commit()

                current_app.logger.info(
                    f"Sync task {self.task_id}: Completed - "
                    f"{self.task.synced_stocks} synced, {self.task.failed_stocks} failed"
                )

            except Exception as e:
                current_app.logger.error(f"Sync task {self.task_id}: Unexpected error: {str(e)}")
                self.task.status = 'failed'
                self.task.error_message = str(e)
                self.task.completed_at = datetime.utcnow()
                db.session.commit()

            finally:
                # Remove from active syncs
                if self.task_id in active_syncs:
                    del active_syncs[self.task_id]

    def _sync_stock(self, hist_data: HistoricalData, settings: HistoricalDataSettings):
        """
        Sync latest candles for a single stock

        Args:
            hist_data: HistoricalData object for the stock
            settings: User's historical data settings
        """
        # Get existing candles
        existing_candles = hist_data.get_candles()

        if not existing_candles:
            current_app.logger.warning(
                f"Sync task {self.task_id}: No existing candles for {hist_data.tradingsymbol}"
            )
            return

        # Find the latest date in existing data
        latest_date_str = max(candle['date'] for candle in existing_candles)
        latest_date = datetime.strptime(latest_date_str, '%Y-%m-%d').date()

        current_app.logger.info(
            f"Sync task {self.task_id}: {hist_data.tradingsymbol} - "
            f"Latest date in DB: {latest_date}"
        )

        # Calculate from_date and to_date for fetching new data
        # Start from the day after the latest date
        from_date = latest_date + timedelta(days=1)
        to_date = date.today()

        # Skip if no new data to fetch
        if from_date > to_date:
            current_app.logger.info(
                f"Sync task {self.task_id}: {hist_data.tradingsymbol} - "
                f"Already up to date"
            )
            self.task.skipped_stocks += 1
            return

        # Get instrument info
        instrument = Instrument.query.filter_by(
            tradingsymbol=hist_data.tradingsymbol,
            exchange='NSE',
            instrument_type='EQ'
        ).first()

        if not instrument:
            current_app.logger.warning(
                f"Sync task {self.task_id}: Instrument not found for {hist_data.tradingsymbol}"
            )
            return

        try:
            # Fetch new candles from Kite API
            current_app.logger.info(
                f"Sync task {self.task_id}: Fetching {hist_data.tradingsymbol} "
                f"from {from_date} to {to_date}"
            )

            new_candles_raw = self.kite.historical_data(
                instrument_token=instrument.instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=self.task.interval,
                continuous=False,
                oi=False
            )

            if not new_candles_raw:
                current_app.logger.info(
                    f"Sync task {self.task_id}: No new candles for {hist_data.tradingsymbol}"
                )
                self.task.skipped_stocks += 1
                return

            # Convert new candles to our format
            new_candles = []
            for candle in new_candles_raw:
                new_candles.append({
                    'date': candle['date'].strftime('%Y-%m-%d'),
                    'open': float(candle['open']),
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'close': float(candle['close']),
                    'volume': int(candle['volume']),
                    'oi': int(candle.get('oi', 0))
                })

            # Merge new candles with existing candles
            # Create a dict for quick lookup by date
            candles_dict = {candle['date']: candle for candle in existing_candles}

            # Add/update with new candles (this avoids duplicates)
            for new_candle in new_candles:
                candles_dict[new_candle['date']] = new_candle

            # Convert back to sorted list
            merged_candles = sorted(
                candles_dict.values(),
                key=lambda x: x['date']
            )

            # Update the database
            hist_data.set_candles(merged_candles)
            hist_data.last_downloaded = datetime.utcnow()

            self.task.new_candles_added += len(new_candles)

            current_app.logger.info(
                f"Sync task {self.task_id}: {hist_data.tradingsymbol} - "
                f"Added {len(new_candles)} new candles "
                f"(total: {len(merged_candles)})"
            )

        except Exception as e:
            current_app.logger.error(
                f"Sync task {self.task_id}: Error fetching data for {hist_data.tradingsymbol}: {str(e)}"
            )
            raise
