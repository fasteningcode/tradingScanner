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

        # Log database path being used for debugging
        current_app.logger.info(f"Task {self.task_id}: Using database: {current_app.config.get('SQLALCHEMY_DATABASE_URI')}")

        # Start download in background thread
        # Kite client will be initialized within the background thread's app context
        thread = threading.Thread(target=self._download_worker, daemon=True, name=f"DownloadWorker-{self.task_id}")
        active_downloads[self.task_id] = self
        thread.start()

        current_app.logger.info(f"Started download task {self.task_id} in background thread (Thread: {thread.name})")

        # Wait briefly to verify thread actually started
        import time
        time.sleep(0.5)

        # Check if task status was updated by worker
        db.session.expire(self.task)
        self.task = DownloadTask.query.get(self.task_id)
        if self.task.status == 'pending' and self.task.total_stocks == 0:
            current_app.logger.warning(f"Task {self.task_id}: Worker thread may not have started properly - status still pending after 0.5s")
        else:
            current_app.logger.info(f"Task {self.task_id}: Worker thread started successfully - status: {self.task.status}, total_stocks: {self.task.total_stocks}")

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
        import threading

        # IMPORTANT: Must enter app context FIRST before any current_app access
        # Run within Flask app context
        with self.app.app_context():
            current_app.logger.info(f"Task {self.task_id}: Worker thread started (Thread ID: {threading.current_thread().ident}, Name: {threading.current_thread().name})")
            current_app.logger.info(f"Task {self.task_id}: Entered Flask app context")
            current_app.logger.info(f"Task {self.task_id}: Database URI: {current_app.config.get('SQLALCHEMY_DATABASE_URI')}")

            try:
                # Re-initialize Kite client within Flask app context
                # This ensures the client works correctly in the background thread
                current_app.logger.info(f"Task {self.task_id}: Loading user and Kite credentials...")
                self.user = User.query.get(self.task.user_id)
                if not self.user or not self.user.kite_access_token:
                    error_msg = 'User not found or Kite access token not available'
                    current_app.logger.error(f"Task {self.task_id}: {error_msg}")
                    self.task.status = 'failed'
                    self.task.error_message = error_msg
                    db.session.commit()
                    return

                current_app.logger.info(f"Task {self.task_id}: User found: {self.user.username}, has token: {bool(self.user.kite_access_token)}")

                try:
                    current_app.logger.info(f"Task {self.task_id}: Initializing Kite client...")
                    self.kite = get_kite_client(access_token=self.user.kite_access_token)
                    current_app.logger.info(f"Task {self.task_id}: Kite client initialized successfully")
                except Exception as e:
                    error_msg = f'Failed to initialize Kite client: {str(e)}'
                    current_app.logger.error(f"Task {self.task_id}: {error_msg}")
                    self.task.status = 'failed'
                    self.task.error_message = error_msg
                    db.session.commit()
                    return

                # Update task status to running
                current_app.logger.info(f"Task {self.task_id}: Updating status to 'running'...")
                self.task.status = 'running'
                if not self.task.started_at:
                    self.task.started_at = datetime.utcnow()
                db.session.commit()
                current_app.logger.info(f"Task {self.task_id}: Status updated to 'running'")

                # Test historical data API access before starting
                current_app.logger.info(f"Task {self.task_id}: Testing historical data API access...")
                try:
                    test_instrument = Instrument.query.filter_by(
                        exchange='NSE',
                        instrument_type='EQ'
                    ).first()

                    if test_instrument:
                        from datetime import timedelta
                        # FIX: Use known good date instead of system date
                        test_date = datetime(2024, 11, 1)  # November 1, 2024 - known trading day
                        current_app.logger.info(f"Task {self.task_id}: Testing with instrument: {test_instrument.tradingsymbol} (token: {test_instrument.instrument_token})")
                        current_app.logger.info(f"Task {self.task_id}: Instrument exchange: {test_instrument.exchange}, type: {test_instrument.instrument_type}")
                        current_app.logger.info(f"Task {self.task_id}: Test date range: {test_date} to {test_date}")

                        # Construct API URL for logging
                        api_url = f"https://api.kite.trade/instruments/historical/{test_instrument.instrument_token}/day"
                        api_params = {
                            "from": test_date.strftime("%Y-%m-%d"),
                            "to": test_date.strftime("%Y-%m-%d"),
                            "instrument_token": test_instrument.instrument_token
                        }
                        current_app.logger.info(f"Task {self.task_id}: API URL: {api_url}")
                        current_app.logger.info(f"Task {self.task_id}: API Params: {api_params}")

                        # Make the API call
                        test_result = self.kite.historical_data(
                            instrument_token=test_instrument.instrument_token,
                            from_date=test_date,
                            to_date=test_date,
                            interval='day'
                        )

                        # Log successful response
                        current_app.logger.info(f"Task {self.task_id}: API Response received successfully")
                        current_app.logger.info(f"Task {self.task_id}: Response data: {len(test_result) if test_result else 0} candles")
                        if test_result and len(test_result) > 0:
                            current_app.logger.info(f"Task {self.task_id}: Sample candle: {test_result[0]}")
                        current_app.logger.info(f"Task {self.task_id}: Historical data API test passed - Got {len(test_result) if test_result else 0} candles")
                except Exception as e:
                    # Log the ACTUAL error for debugging
                    current_app.logger.error(f"Task {self.task_id}: ========================================")
                    current_app.logger.error(f"Task {self.task_id}: API CALL FAILED")
                    current_app.logger.error(f"Task {self.task_id}: Error type: {type(e).__name__}")
                    current_app.logger.error(f"Task {self.task_id}: Error message: {str(e)}")
                    current_app.logger.error(f"Task {self.task_id}: Instrument token that failed: {test_instrument.instrument_token if test_instrument else 'N/A'}")
                    current_app.logger.error(f"Task {self.task_id}: Instrument symbol: {test_instrument.tradingsymbol if test_instrument else 'N/A'}")

                    # Try to log additional error details if available
                    if hasattr(e, 'response'):
                        current_app.logger.error(f"Task {self.task_id}: HTTP Response Status: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'}")
                        current_app.logger.error(f"Task {self.task_id}: HTTP Response Body: {e.response.text if hasattr(e.response, 'text') else 'N/A'}")
                    current_app.logger.error(f"Task {self.task_id}: ========================================")

                    # Changed logic: Don't fail on "invalid token" error - it might be a bad instrument token
                    # Instead, try a different instrument or skip the test
                    if "invalid token" in str(e).lower():
                        current_app.logger.warning(f"Task {self.task_id}: Test instrument token invalid. This might be a stale instrument. Trying to continue with download...")
                        # Don't raise exception - continue with download and let it try other instruments
                    else:
                        current_app.logger.warning(f"Task {self.task_id}: Historical data API test failed, but continuing anyway: {str(e)}")
                        # Continue anyway - might be a transient error or date issue

                # Get list of stocks to download
                current_app.logger.info(f"Task {self.task_id}: Getting list of stocks to download...")
                stocks = self._get_stocks_to_download()
                current_app.logger.info(f"Task {self.task_id}: Found {len(stocks)} stocks to download")

                self.task.total_stocks = len(stocks)
                db.session.commit()
                current_app.logger.info(f"Task {self.task_id}: Updated task.total_stocks = {len(stocks)}")

                if len(stocks) == 0:
                    current_app.logger.warning(f"Task {self.task_id}: No stocks found to download!")
                    self.task.status = 'completed'
                    self.task.completed_at = datetime.utcnow()
                    db.session.commit()
                    return

                current_app.logger.info(f"Task {self.task_id}: Starting download of {len(stocks)} stocks...")

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
                    if self.task.total_stocks > 0:
                        self.task.progress_percentage = (self.task.completed_stocks + self.task.failed_stocks + self.task.skipped_stocks) / self.task.total_stocks * 100
                        current_app.logger.debug(f"Task {self.task_id}: Progress updated: {self.task.progress_percentage:.2f}% ({self.task.completed_stocks + self.task.failed_stocks + self.task.skipped_stocks}/{self.task.total_stocks})")
                    else:
                        current_app.logger.warning(f"Task {self.task_id}: total_stocks is 0, cannot calculate progress percentage")
                        self.task.progress_percentage = 0.0
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
        current_app.logger.info(f"Task {self.task_id}: ========================================")
        current_app.logger.info(f"Task {self.task_id}: Starting download for {instrument.tradingsymbol}")
        current_app.logger.info(f"Task {self.task_id}: Instrument details:")
        current_app.logger.info(f"Task {self.task_id}:   - Symbol: {instrument.tradingsymbol}")
        current_app.logger.info(f"Task {self.task_id}:   - Exchange: {instrument.exchange}")
        current_app.logger.info(f"Task {self.task_id}:   - Instrument Token: {instrument.instrument_token}")
        current_app.logger.info(f"Task {self.task_id}:   - Instrument Type: {instrument.instrument_type}")

        log = DownloadLog(
            task_id=self.task_id,
            instrument_id=instrument.id,
            symbol=instrument.tradingsymbol,
            status='pending',
            started_at=datetime.utcnow()
        )
        db.session.add(log)
        db.session.commit()
        current_app.logger.info(f"Task {self.task_id}: Created download log entry")

        try:
            # Check if data already exists (new JSON schema)
            current_app.logger.info(f"Task {self.task_id}: Checking if data already exists for {instrument.tradingsymbol}...")
            existing_data = HistoricalData.query.filter_by(
                tradingsymbol=instrument.tradingsymbol,
                interval=self.task.interval
            ).first()

            if existing_data:
                # Data already exists, skip (for now - could merge later)
                candle_count = existing_data.get_candle_count()
                current_app.logger.info(f"Task {self.task_id}: SKIPPED - {instrument.tradingsymbol} already has {candle_count} candles")
                log.status = 'skipped'
                log.records_downloaded = candle_count
                log.completed_at = datetime.utcnow()
                self.task.skipped_stocks += 1
                db.session.commit()
                return

            # Download data from Kite
            from_date = self.task.from_date
            to_date = self.task.to_date
            current_app.logger.info(f"Task {self.task_id}: Date range: {from_date} to {to_date}")
            current_app.logger.info(f"Task {self.task_id}: Interval: {self.task.interval}")

            # Split into smaller chunks if date range is large (avoid API timeouts)
            chunks = self._split_date_range(from_date, to_date, self.task.interval)
            current_app.logger.info(f"Task {self.task_id}: Date range split into {len(chunks)} chunk(s)")

            all_candles = []
            for chunk_idx, (chunk_from, chunk_to) in enumerate(chunks, 1):
                try:
                    current_app.logger.info(f"Task {self.task_id}: Downloading chunk {chunk_idx}/{len(chunks)}: {chunk_from} to {chunk_to}")

                    # Construct API URL for logging
                    api_url = f"https://api.kite.trade/instruments/historical/{instrument.instrument_token}/{self.task.interval}"
                    api_params = {
                        "from": chunk_from.strftime("%Y-%m-%d"),
                        "to": chunk_to.strftime("%Y-%m-%d"),
                        "instrument_token": instrument.instrument_token,
                        "interval": self.task.interval
                    }
                    current_app.logger.info(f"Task {self.task_id}: API URL: {api_url}")
                    current_app.logger.info(f"Task {self.task_id}: API Params: {api_params}")

                    # Make API call
                    candles = self.kite.historical_data(
                        instrument_token=instrument.instrument_token,
                        from_date=chunk_from,
                        to_date=chunk_to,
                        interval=self.task.interval
                    )

                    current_app.logger.info(f"Task {self.task_id}: API Response: Received {len(candles) if candles else 0} candles")
                    if candles and len(candles) > 0:
                        current_app.logger.info(f"Task {self.task_id}: Sample candle data: {candles[0]}")

                    all_candles.extend(candles)
                    log.api_calls_made += 1
                    self.task.total_api_calls += 1
                    current_app.logger.info(f"Task {self.task_id}: Total candles accumulated: {len(all_candles)}")

                    # Rate limit between chunks
                    if len(chunks) > 1:
                        sleep_time = 1.0 / self.task.requests_per_second
                        current_app.logger.info(f"Task {self.task_id}: Rate limiting: sleeping for {sleep_time:.2f}s")
                        time.sleep(sleep_time)

                except Exception as e:
                    error_msg = str(e)
                    current_app.logger.error(f"Task {self.task_id}: ========================================")
                    current_app.logger.error(f"Task {self.task_id}: ERROR downloading chunk {chunk_idx}/{len(chunks)}")
                    current_app.logger.error(f"Task {self.task_id}: Chunk date range: {chunk_from} to {chunk_to}")
                    current_app.logger.error(f"Task {self.task_id}: Error type: {type(e).__name__}")
                    current_app.logger.error(f"Task {self.task_id}: Error message: {error_msg}")

                    # Try to log additional error details if available
                    if hasattr(e, 'response'):
                        current_app.logger.error(f"Task {self.task_id}: HTTP Response Status: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'}")
                        current_app.logger.error(f"Task {self.task_id}: HTTP Response Body: {e.response.text if hasattr(e.response, 'text') else 'N/A'}")
                    current_app.logger.error(f"Task {self.task_id}: ========================================")

                    # Check if this is a historical data permissions error
                    if "invalid token" in error_msg.lower():
                        current_app.logger.error(f"Task {self.task_id}: CRITICAL - Invalid instrument token error")
                        current_app.logger.error(f"Task {self.task_id}: This instrument token appears to be invalid: {instrument.instrument_token}")
                        current_app.logger.error(f"Task {self.task_id}: Skipping {instrument.tradingsymbol} and continuing with next stock")
                        # Don't raise - just skip this stock and continue
                        break

                    # Continue with next chunk for other errors
                    current_app.logger.warning(f"Task {self.task_id}: Continuing with next chunk...")
                    continue

            if not all_candles:
                current_app.logger.warning(f"Task {self.task_id}: FAILED - No data returned from API for {instrument.tradingsymbol}")
                log.status = 'failed'
                log.error_message = 'No data returned from API'
                log.completed_at = datetime.utcnow()
                db.session.commit()
                return

            # Store candles in database (JSON format)
            current_app.logger.info(f"Task {self.task_id}: Storing {len(all_candles)} candles in database...")
            self._store_candles(instrument.tradingsymbol, all_candles, self.task.interval)
            current_app.logger.info(f"Task {self.task_id}: Successfully stored candles")

            log.status = 'success'
            log.records_downloaded = len(all_candles)
            log.completed_at = datetime.utcnow()
            self.task.total_records_downloaded += len(all_candles)
            db.session.commit()

            current_app.logger.info(f"Task {self.task_id}: SUCCESS - Downloaded {len(all_candles)} candles for {instrument.tradingsymbol}")
            current_app.logger.info(f"Task {self.task_id}: ========================================")

        except Exception as e:
            current_app.logger.error(f"Task {self.task_id}: ========================================")
            current_app.logger.error(f"Task {self.task_id}: FATAL ERROR downloading {instrument.tradingsymbol}")
            current_app.logger.error(f"Task {self.task_id}: Error type: {type(e).__name__}")
            current_app.logger.error(f"Task {self.task_id}: Error message: {str(e)}")
            current_app.logger.error(f"Task {self.task_id}: ========================================")

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
        # Use today's date as the end date for historical data
        # This ensures we always download the most recent data available
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

    # Log the calculated date range
    from flask import current_app
    current_app.logger.info(f"Date range calculation:")
    current_app.logger.info(f"  - Today's date: {date.today()}")
    current_app.logger.info(f"  - Date preset: {settings.date_preset}")
    current_app.logger.info(f"  - Calculated FROM date: {from_date}")
    current_app.logger.info(f"  - Calculated TO date: {to_date}")
    current_app.logger.info(f"  - Total days: {(to_date - from_date).days}")

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

    OPTIMIZED: Uses COUNT queries and sampling instead of loading all records
    to prevent request stalling with large datasets (e.g., 481+ records)

    Args:
        user_id: Optional user ID to filter by user's stocks

    Returns:
        Dictionary with storage statistics
    """
    from sqlalchemy import func

    # Use COUNT query instead of loading all records into memory
    # This is MUCH faster for large datasets
    stocks_with_data = HistoricalData.query.count()

    # Get total NIFTY 500 stocks
    total_nifty500 = Instrument.query.filter_by(
        exchange='NSE',
        instrument_type='EQ',
        is_nifty500=True
    ).count()

    # For empty database, return zeros immediately
    if stocks_with_data == 0:
        return {
            'total_records': 0,
            'stocks_with_data': 0,
            'total_stocks': total_nifty500,
            'coverage_percentage': 0,
            'earliest_date': None,
            'latest_date': None,
            'estimated_size_mb': 0
        }

    # Only load a sample of records to calculate averages (first 10 records)
    # This avoids loading all 481+ records with JSON data into memory
    sample_data = HistoricalData.query.limit(10).all()

    # Calculate average candles per stock from sample
    avg_candles = sum(data.get_candle_count() for data in sample_data) / len(sample_data) if sample_data else 0
    total_candles = int(avg_candles * stocks_with_data)

    # Calculate average JSON size from sample
    avg_json_size = sum(len(data.candlestick_data or '') for data in sample_data) / len(sample_data) if sample_data else 0
    total_json_size = avg_json_size * stocks_with_data
    estimated_size_mb = total_json_size / (1024 * 1024)

    # Get date ranges from first and last records (ordered by created_on timestamp)
    # This is much faster than iterating through all records
    first_record = HistoricalData.query.order_by(HistoricalData.created_on.asc()).first()
    last_record = HistoricalData.query.order_by(HistoricalData.created_on.desc()).first()

    earliest_date = None
    latest_date = None

    if first_record:
        early, _ = first_record.get_date_range()
        earliest_date = early

    if last_record:
        _, late = last_record.get_date_range()
        latest_date = late

    return {
        'total_records': total_candles,  # Estimated total candles based on sample
        'stocks_with_data': stocks_with_data,
        'total_stocks': total_nifty500,
        'coverage_percentage': round((stocks_with_data / total_nifty500 * 100), 2) if total_nifty500 > 0 else 0,
        'earliest_date': earliest_date,
        'latest_date': latest_date,
        'estimated_size_mb': round(estimated_size_mb, 2)
    }
