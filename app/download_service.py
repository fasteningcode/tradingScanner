"""
Historical Data Download Service

This module handles downloading historical candlestick data from Kite Connect API
with progress tracking, rate limiting, and error handling.
"""

import time
import threading
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from flask import current_app
from app import db
from app.models import (
    Instrument, HistoricalData, HistoricalDataSettings,
    DownloadTask, DownloadLog, User
)
from app.kite_auth import get_kite_client


# Global dictionary to store active download threads
active_downloads = {}


class HistoricalDataDownloader:
    """Service class to handle historical data downloads"""

    def __init__(self, task_id: int):
        """
        Initialize downloader with a task ID

        Args:
            task_id: ID of the DownloadTask to process
        """
        self.task_id = task_id
        self.task = None
        self.user = None
        self.kite = None
        self.should_stop = False
        self.app = None  # Will store Flask app instance

    def start_download(self):
        """Start the download process in a background thread"""
        # Store Flask app instance for background thread
        self.app = current_app._get_current_object()

        # Load task from database
        self.task = DownloadTask.query.get(self.task_id)
        if not self.task:
            raise ValueError(f"Task {self.task_id} not found")

        if self.task.status not in ['pending', 'paused']:
            raise ValueError(f"Task {self.task_id} is already {self.task.status}")

        # Load user
        self.user = User.query.get(self.task.user_id)
        if not self.user or not self.user.kite_access_token:
            self.task.status = 'failed'
            self.task.error_message = 'User not found or Kite access token not available'
            db.session.commit()
            raise ValueError(self.task.error_message)

        # Initialize Kite client
        try:
            self.kite = get_kite_client(access_token=self.user.kite_access_token)
        except Exception as e:
            self.task.status = 'failed'
            self.task.error_message = f'Failed to initialize Kite client: {str(e)}'
            db.session.commit()
            raise

        # Start download in background thread
        thread = threading.Thread(target=self._download_worker, daemon=True)
        active_downloads[self.task_id] = self
        thread.start()

        current_app.logger.info(f"Started download task {self.task_id} in background thread")

    def pause_download(self):
        """Pause the running download"""
        self.should_stop = True
        self.task.status = 'paused'
        self.task.paused_at = datetime.utcnow()
        db.session.commit()
        current_app.logger.info(f"Paused download task {self.task_id}")

    def cancel_download(self):
        """Cancel the running download"""
        self.should_stop = True
        self.task.status = 'cancelled'
        self.task.completed_at = datetime.utcnow()
        db.session.commit()
        current_app.logger.info(f"Cancelled download task {self.task_id}")

    def _download_worker(self):
        """Main worker function that runs in background thread"""
        # Run within Flask app context
        with self.app.app_context():
            try:
                # Update task status to running
                self.task.status = 'running'
                if not self.task.started_at:
                    self.task.started_at = datetime.utcnow()
                db.session.commit()

                # Get list of stocks to download
                stocks = self._get_stocks_to_download()
                self.task.total_stocks = len(stocks)
                db.session.commit()

                current_app.logger.info(f"Task {self.task_id}: Downloading {len(stocks)} stocks")

                # Process each stock
                for i, instrument in enumerate(stocks):
                    if self.should_stop:
                        current_app.logger.info(f"Task {self.task_id}: Stopped at stock {i}/{len(stocks)}")
                        break

                    # Update current stock
                    self.task.current_stock_symbol = instrument.tradingsymbol
                    self.task.current_stock_id = instrument.id
                    db.session.commit()

                    # Download data for this stock
                    try:
                        self._download_stock_data(instrument)
                        self.task.completed_stocks += 1
                    except Exception as e:
                        current_app.logger.error(f"Task {self.task_id}: Error downloading {instrument.tradingsymbol}: {str(e)}")
                        self.task.failed_stocks += 1
                        self.task.error_count += 1

                    # Update progress
                    self.task.progress_percentage = (self.task.completed_stocks + self.task.failed_stocks + self.task.skipped_stocks) / self.task.total_stocks * 100
                    db.session.commit()

                    # Apply rate limiting
                    self._apply_rate_limit()

                # Mark task as completed if not stopped
                if not self.should_stop:
                    self.task.status = 'completed'
                    self.task.completed_at = datetime.utcnow()
                    self.task.progress_percentage = 100.0
                    db.session.commit()
                    current_app.logger.info(f"Task {self.task_id}: Completed successfully")

            except Exception as e:
                current_app.logger.error(f"Task {self.task_id}: Fatal error: {str(e)}")
                self.task.status = 'failed'
                self.task.error_message = str(e)
                self.task.completed_at = datetime.utcnow()
                db.session.commit()

            finally:
                # Remove from active downloads
                if self.task_id in active_downloads:
                    del active_downloads[self.task_id]

    def _get_stocks_to_download(self) -> List[Instrument]:
        """
        Get list of stocks to download based on task status

        Returns:
            List of Instrument objects
        """
        query = Instrument.query.filter_by(
            exchange='NSE',
            instrument_type='EQ',
            is_nifty500=True
        )

        # If resuming, skip already processed stocks
        if self.task.current_stock_id:
            query = query.filter(Instrument.id > self.task.current_stock_id)

        return query.order_by(Instrument.id).all()

    def _download_stock_data(self, instrument: Instrument):
        """
        Download historical data for a single stock

        Args:
            instrument: Instrument object to download data for
        """
        log = DownloadLog(
            task_id=self.task_id,
            instrument_id=instrument.id,
            symbol=instrument.tradingsymbol,
            status='pending',
            started_at=datetime.utcnow()
        )
        db.session.add(log)
        db.session.commit()

        try:
            # Check if data already exists (new JSON schema)
            existing_data = HistoricalData.query.filter_by(
                tradingsymbol=instrument.tradingsymbol,
                interval=self.task.interval
            ).first()

            if existing_data:
                # Data already exists, skip (for now - could merge later)
                candle_count = existing_data.get_candle_count()
                log.status = 'skipped'
                log.records_downloaded = candle_count
                log.completed_at = datetime.utcnow()
                self.task.skipped_stocks += 1
                db.session.commit()
                current_app.logger.debug(f"Task {self.task_id}: Skipped {instrument.tradingsymbol} (already has {candle_count} candles)")
                return

            # Download data from Kite
            from_date = self.task.from_date
            to_date = self.task.to_date

            # Split into smaller chunks if date range is large (avoid API timeouts)
            chunks = self._split_date_range(from_date, to_date, self.task.interval)

            all_candles = []
            for chunk_from, chunk_to in chunks:
                try:
                    candles = self.kite.historical_data(
                        instrument_token=instrument.instrument_token,
                        from_date=chunk_from,
                        to_date=chunk_to,
                        interval=self.task.interval
                    )
                    all_candles.extend(candles)
                    log.api_calls_made += 1
                    self.task.total_api_calls += 1

                    # Rate limit between chunks
                    if len(chunks) > 1:
                        time.sleep(1.0 / self.task.requests_per_second)

                except Exception as e:
                    current_app.logger.warning(f"Task {self.task_id}: Error downloading chunk {chunk_from} to {chunk_to} for {instrument.tradingsymbol}: {str(e)}")
                    # Continue with next chunk
                    continue

            if not all_candles:
                log.status = 'failed'
                log.error_message = 'No data returned from API'
                log.completed_at = datetime.utcnow()
                db.session.commit()
                return

            # Store candles in database (JSON format)
            self._store_candles(instrument.tradingsymbol, all_candles, self.task.interval)

            log.status = 'success'
            log.records_downloaded = len(all_candles)
            log.completed_at = datetime.utcnow()
            self.task.total_records_downloaded += len(all_candles)
            db.session.commit()

            current_app.logger.debug(f"Task {self.task_id}: Downloaded {len(all_candles)} candles for {instrument.tradingsymbol}")

        except Exception as e:
            log.status = 'failed'
            log.error_message = str(e)
            log.completed_at = datetime.utcnow()
            db.session.commit()
            raise

    def _split_date_range(self, from_date: date, to_date: date, interval: str) -> List[tuple]:
        """
        Split large date ranges into smaller chunks to avoid API timeouts

        Args:
            from_date: Start date
            to_date: End date
            interval: Candle interval

        Returns:
            List of (from_date, to_date) tuples
        """
        # Determine chunk size based on interval
        if interval in ['minute', '3minute', '5minute']:
            chunk_days = 60  # 60 days for minute intervals
        elif interval in ['10minute', '15minute', '30minute']:
            chunk_days = 100  # 100 days for mid intervals
        elif interval == '60minute':
            chunk_days = 200  # 200 days for hourly
        else:  # day
            chunk_days = 2000  # 2000 days for daily (no chunking needed usually)

        chunks = []
        current_from = from_date

        while current_from < to_date:
            current_to = min(
                current_from + timedelta(days=chunk_days),
                to_date
            )
            chunks.append((current_from, current_to))
            current_from = current_to + timedelta(days=1)

        return chunks

    def _store_candles(self, tradingsymbol: str, candles: List[Dict[str, Any]], interval: str):
        """
        Store candles in database as JSON (one row per stock per interval)

        Args:
            tradingsymbol: Trading symbol of the instrument
            candles: List of candle dictionaries from Kite API
            interval: Candle interval
        """
        import json

        # Convert Kite API candles to our JSON format
        candles_json = []
        for candle in candles:
            # Validate candle data
            if not all(key in candle for key in ['date', 'open', 'high', 'low', 'close']):
                current_app.logger.warning(f"Invalid candle data: {candle}")
                continue

            # Format: {"date": "2024-01-01", "open": 100.0, "high": 105.0, "low": 99.0, "close": 103.0, "volume": 1000, "oi": 0}
            candles_json.append({
                'date': candle['date'].strftime('%Y-%m-%d') if hasattr(candle['date'], 'strftime') else str(candle['date']).split(' ')[0],
                'open': float(candle['open']),
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close']),
                'volume': int(candle.get('volume', 0)),
                'oi': int(candle.get('oi', 0))
            })

        if not candles_json:
            current_app.logger.warning(f"No valid candles to store for {tradingsymbol}")
            return

        try:
            # Check if record exists
            existing = HistoricalData.query.filter_by(
                tradingsymbol=tradingsymbol,
                interval=interval
            ).first()

            if existing:
                # Replace entire JSON (as per user preference)
                existing.set_candles(candles_json)
                existing.last_downloaded = datetime.utcnow()
            else:
                # Create new record
                new_data = HistoricalData(
                    tradingsymbol=tradingsymbol,
                    interval=interval,
                    candlestick_data=json.dumps(candles_json),
                    last_downloaded=datetime.utcnow(),
                    created_on=datetime.utcnow(),
                    updated_on=datetime.utcnow()
                )
                db.session.add(new_data)

            db.session.commit()
            current_app.logger.debug(f"Stored {len(candles_json)} candles for {tradingsymbol} ({interval})")

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to store candles for {tradingsymbol}: {str(e)}")
            raise

    def _apply_rate_limit(self):
        """Apply rate limiting based on task configuration"""
        sleep_time = 1.0 / self.task.requests_per_second
        time.sleep(sleep_time)

    @staticmethod
    def calculate_date_range(settings: HistoricalDataSettings) -> tuple:
        """
        Calculate actual date range based on preset or custom dates

        Args:
            settings: HistoricalDataSettings object

        Returns:
            Tuple of (from_date, to_date)
        """
        to_date = date.today()

        if settings.date_preset == 'custom':
            if settings.from_date and settings.to_date:
                return (settings.from_date, settings.to_date)
            else:
                # Fallback to 1 month if custom dates not set
                from_date = to_date - timedelta(days=30)
                return (from_date, to_date)

        # Calculate from_date based on preset
        preset_days = {
            '1day': 1,
            '1week': 7,
            '1month': 30,
            '3months': 90,
            '6months': 180,
            '1year': 365,
            '5years': 365 * 5,
            '10years': 365 * 10
        }

        days = preset_days.get(settings.date_preset, 30)
        from_date = to_date - timedelta(days=days)

        return (from_date, to_date)


def create_download_task(user_id: int) -> Optional[DownloadTask]:
    """
    Create a new download task for a user

    Args:
        user_id: ID of the user

    Returns:
        DownloadTask object or None if settings not found
    """
    # Get user's historical data settings
    settings = HistoricalDataSettings.query.filter_by(user_id=user_id).first()
    if not settings:
        return None

    # Calculate date range
    from_date, to_date = HistoricalDataDownloader.calculate_date_range(settings)

    # Create task
    task = DownloadTask(
        user_id=user_id,
        interval=settings.candle_interval,
        from_date=from_date,
        to_date=to_date,
        requests_per_second=settings.requests_per_second,
        status='pending',
        progress_percentage=0.0,
        total_stocks=0,
        completed_stocks=0,
        failed_stocks=0,
        skipped_stocks=0
    )

    db.session.add(task)
    db.session.commit()

    return task


def get_active_task(user_id: int) -> Optional[DownloadTask]:
    """
    Get the active download task for a user

    Args:
        user_id: ID of the user

    Returns:
        DownloadTask object or None
    """
    return DownloadTask.query.filter_by(
        user_id=user_id
    ).filter(
        DownloadTask.status.in_(['pending', 'running', 'paused'])
    ).order_by(DownloadTask.created_at.desc()).first()


def get_storage_stats(user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Calculate storage statistics for historical data (JSON schema)

    Args:
        user_id: Optional user ID to filter by user's stocks

    Returns:
        Dictionary with storage statistics
    """
    # Get all historical data records
    all_data = HistoricalData.query.all()

    # Calculate total candles across all stocks
    total_candles = sum(data.get_candle_count() for data in all_data)

    # Get unique stocks with data
    stocks_with_data = len(all_data)

    # Get date ranges
    earliest_date = None
    latest_date = None
    for data in all_data:
        early, late = data.get_date_range()
        if early:
            if not earliest_date or early < earliest_date:
                earliest_date = early
        if late:
            if not latest_date or late > latest_date:
                latest_date = late

    # Get total NIFTY 500 stocks
    total_nifty500 = Instrument.query.filter_by(
        exchange='NSE',
        instrument_type='EQ',
        is_nifty500=True
    ).count()

    # Calculate actual storage size
    total_json_size = sum(len(data.candlestick_data) for data in all_data)
    estimated_size_mb = total_json_size / (1024 * 1024)

    return {
        'total_records': total_candles,  # Total candles
        'stocks_with_data': stocks_with_data,
        'total_stocks': total_nifty500,
        'coverage_percentage': round((stocks_with_data / total_nifty500 * 100), 2) if total_nifty500 > 0 else 0,
        'earliest_date': earliest_date,
        'latest_date': latest_date,
        'estimated_size_mb': round(estimated_size_mb, 2)
    }
