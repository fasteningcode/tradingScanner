"""
Scanner Service

This service handles stock scanner execution and profile management.
Includes complete filter chain execution with detailed progress tracking.
"""

import threading
import json
from typing import Optional, Dict, List
from datetime import datetime
from flask import current_app
from app import db
from app.models import ScannerProfile, ScannerTask, ScanResultStock, Instrument, SubSector, HistoricalData

# Dictionary to track running scanner tasks
_running_tasks = {}


# ========================================
# Moving Average Calculation Helpers
# ========================================

def calculate_sma(candles, period):
    """
    Calculate Simple Moving Average (SMA) for given period

    Args:
        candles: List of candle dicts with 'close' prices (sorted oldest to newest)
        period: Number of periods (e.g., 9, 20, 50)

    Returns:
        float: SMA value or None if insufficient data
    """
    if not candles or len(candles) < period:
        return None

    # Take the last 'period' candles and calculate average of close prices
    recent_candles = candles[-period:]
    close_prices = [c.get('close') for c in recent_candles if c.get('close') is not None]

    if len(close_prices) < period:
        return None

    return sum(close_prices) / period


def calculate_ema(candles, period):
    """
    Calculate Exponential Moving Average (EMA) for given period

    Args:
        candles: List of candle dicts with 'close' prices (sorted oldest to newest)
        period: Number of periods (e.g., 9, 20, 50)

    Returns:
        float: EMA value or None if insufficient data
    """
    if not candles or len(candles) < period:
        return None

    close_prices = [c.get('close') for c in candles if c.get('close') is not None]

    if len(close_prices) < period:
        return None

    # Calculate multiplier: 2 / (period + 1)
    multiplier = 2 / (period + 1)

    # Start with SMA as the first EMA value
    ema = sum(close_prices[:period]) / period

    # Calculate EMA for remaining values
    for price in close_prices[period:]:
        ema = (price - ema) * multiplier + ema

    return ema


def start_scan(user_id: int, profile_id: int, app=None) -> Optional[int]:
    """
    Start scanner task in background

    Args:
        user_id: User ID
        profile_id: Scanner profile ID
        app: Flask app instance

    Returns:
        Task ID if started successfully, None otherwise
    """
    try:
        current_app.logger.info(f'Starting scanner for user {user_id}, profile {profile_id}')

        # Verify profile exists and belongs to user
        profile = ScannerProfile.query.filter_by(
            id=profile_id,
            user_id=user_id
        ).first()

        if not profile:
            current_app.logger.error(f'Profile {profile_id} not found for user {user_id}')
            return None

        # Create task record with criteria snapshot
        task = ScannerTask(
            user_id=user_id,
            profile_id=profile_id,
            status='pending',
            criteria_snapshot=profile.criteria  # Store the exact criteria at scan time
        )
        db.session.add(task)
        db.session.commit()

        task_id = task.id
        current_app.logger.info(f'Created scanner task {task_id}')

        # Get app context if not provided
        if app is None:
            app = current_app._get_current_object()

        # Start scanner in background thread
        thread = threading.Thread(
            target=_run_scanner,
            args=(task_id, app),
            daemon=True
        )
        thread.start()
        _running_tasks[task_id] = thread

        current_app.logger.info(f'Scanner task {task_id} thread started')
        return task_id

    except Exception as e:
        current_app.logger.error(f'Error starting scanner: {str(e)}', exc_info=True)
        return None


def get_scan_status(user_id: int) -> Optional[Dict]:
    """
    Get status of the most recent scanner task for a user

    Args:
        user_id: User ID

    Returns:
        Task status dictionary or None if no task found
    """
    try:
        task = ScannerTask.query.filter_by(user_id=user_id).order_by(
            ScannerTask.created_at.desc()
        ).first()

        if task:
            return task.to_dict()
        return None

    except Exception as e:
        current_app.logger.error(f'Error getting scan status: {str(e)}', exc_info=True)
        return None


def cancel_scan(task_id: int) -> bool:
    """
    Cancel a running scanner task

    Args:
        task_id: Task ID

    Returns:
        True if cancelled successfully, False otherwise
    """
    try:
        task = ScannerTask.query.get(task_id)
        if task and task.status == 'running':
            task.status = 'cancelled'
            task.completed_at = datetime.utcnow()
            db.session.commit()
            current_app.logger.info(f'Scanner task {task_id} cancelled')
            return True
        return False

    except Exception as e:
        current_app.logger.error(f'Error cancelling scanner: {str(e)}', exc_info=True)
        return False


def _run_scanner(task_id: int, app):
    """
    Run scanner in background thread

    Args:
        task_id: Task ID
        app: Flask app instance
    """
    with app.app_context():
        try:
            current_app.logger.info(f'Scanner task {task_id}: Starting background execution')
            scanner = Scanner(task_id)
            scanner.run()
            current_app.logger.info(f'Scanner task {task_id}: Completed successfully')
        except Exception as e:
            current_app.logger.error(
                f'Scanner task {task_id} failed: {str(e)}',
                exc_info=True
            )
            try:
                task = ScannerTask.query.get(task_id)
                if task:
                    task.status = 'failed'
                    task.error_message = str(e)
                    task.completed_at = datetime.utcnow()
                    db.session.commit()
                    current_app.logger.info(f'Scanner task {task_id}: Marked as failed in database')
            except Exception as db_error:
                current_app.logger.error(
                    f'Scanner task {task_id}: Failed to update task status: {str(db_error)}',
                    exc_info=True
                )
        finally:
            # Remove from running tasks
            if task_id in _running_tasks:
                del _running_tasks[task_id]
                current_app.logger.info(f'Scanner task {task_id}: Removed from running tasks')


class Scanner:
    """Handles scanner execution"""

    def __init__(self, task_id: int):
        self.task_id = task_id
        self.task = ScannerTask.query.get(task_id)
        if not self.task:
            raise ValueError(f'Scanner task {task_id} not found')

    def run(self):
        """
        Execute the scanner with complete filter chain and result storage
        """
        current_app.logger.info(f'Scanner task {self.task_id}: Starting run()')

        try:
            # Update task status to running
            self.task.status = 'running'
            self.task.started_at = datetime.utcnow()
            self.task.progress_message = 'Initializing scanner...'
            db.session.commit()
            current_app.logger.info(f'Scanner task {self.task_id}: Status set to running')

            # Get profile name for progress messages
            profile_name = self.task.profile.name if self.task.profile else 'Unknown'
            self.task.progress_message = f'Starting scan with profile: {profile_name}'
            db.session.commit()

            # Get stocks after Stage/Sector/RS/Volume filters (from _get_stocks_to_scan)
            self.task.progress_message = 'Applying initial filters (Stage, RS, Volume)...'
            db.session.commit()

            stocks = self._get_stocks_to_scan()
            self.task.total_stocks = len(stocks)
            db.session.commit()

            current_app.logger.info(f'Scanner task {self.task_id}: Found {len(stocks)} stocks after initial filters')

            if len(stocks) == 0:
                current_app.logger.warning(f'Scanner task {self.task_id}: No stocks found to scan')
                self.task.status = 'completed'
                self.task.completed_at = datetime.utcnow()
                self.task.progress_message = 'Scan completed: No stocks matched criteria'
                db.session.commit()
                return

            # Parse criteria for MA and Price Action filters
            criteria = {}
            if self.task.profile and self.task.profile.criteria:
                try:
                    criteria = json.loads(self.task.profile.criteria)
                except json.JSONDecodeError:
                    criteria = {}

            enable_ma_filter = criteria.get('enable_ma_filter', False)
            enable_price_action_filter = criteria.get('enable_price_action_filter', False)
            selected_sma = criteria.get('selected_sma', [])
            selected_ema = criteria.get('selected_ema', [])
            selected_price_action_strategies = criteria.get('selected_price_action_strategies', [])
            price_action_lookback_days = criteria.get('price_action_lookback_days', 252)

            # Storage for matched stocks
            matched_results = []

            # Scan each stock with MA and Price Action filters
            self.task.progress_message = f'Analyzing stocks ({len(stocks)} to scan)...'
            db.session.commit()

            for idx, stock in enumerate(stocks):
                try:
                    # Check if task was cancelled
                    db.session.refresh(self.task)
                    if self.task.status == 'cancelled':
                        current_app.logger.info(f'Scanner task {self.task_id} was cancelled')
                        return

                    # Update progress (after refresh, so values are fresh)
                    self.task.current_stock_symbol = stock.tradingsymbol
                    self.task.scanned_stocks += 1
                    self.task.progress_percentage = ((idx + 1) / len(stocks)) * 100
                    self.task.progress_message = f'Scanning: {stock.tradingsymbol} ({idx + 1} of {len(stocks)})'

                    # Commit progress updates immediately to persist counters and prevent loss on next refresh
                    db.session.commit()

                    # Get historical data for MA and Price Action analysis
                    hist_data = HistoricalData.query.filter_by(
                        tradingsymbol=stock.tradingsymbol,
                        interval='day'
                    ).first()

                    if not hist_data:
                        continue

                    candles = hist_data.get_candles()
                    if not candles or len(candles) < 2:
                        continue

                    current_price = candles[-1].get('close')
                    if current_price is None:
                        continue

                    # Apply MA Filter if enabled (Step 4 in pipeline)
                    ma_above = []

                    if enable_ma_filter and (selected_sma or selected_ema):
                        # Check if price is above ALL selected MAs
                        price_above_all_mas = True

                        # Check SMAs
                        if selected_sma:
                            for period in selected_sma:
                                sma_value = calculate_sma(candles, period)
                                if sma_value is None or current_price <= sma_value:
                                    price_above_all_mas = False
                                    break
                                else:
                                    ma_above.append(f'SMA_{period}')

                        # Check EMAs
                        if price_above_all_mas and selected_ema:
                            for period in selected_ema:
                                ema_value = calculate_ema(candles, period)
                                if ema_value is None or current_price <= ema_value:
                                    price_above_all_mas = False
                                    break
                                else:
                                    ma_above.append(f'EMA_{period}')

                        # If stock doesn't pass MA filter, skip it
                        if not price_above_all_mas:
                            continue

                    # Also record common MAs for display (20, 50, 200) if not already checked
                    for period in [20, 50, 200]:
                        if period not in (selected_sma or []):
                            sma_value = calculate_sma(candles, period)
                            if sma_value and current_price > sma_value:
                                ma_above.append(f'SMA_{period}')

                    # Apply Price Action Filter if enabled
                    price_action_pattern = None
                    if enable_price_action_filter and selected_price_action_strategies:
                        passes_price_action = False

                        if len(candles) >= price_action_lookback_days + 50:
                            if 'breakout' in selected_price_action_strategies:
                                if self._is_breakout_pattern(candles, price_action_lookback_days):
                                    passes_price_action = True
                                    price_action_pattern = 'breakout'

                            if 'pullback' in selected_price_action_strategies and not price_action_pattern:
                                if self._is_pullback_pattern(candles, price_action_lookback_days):
                                    passes_price_action = True
                                    price_action_pattern = 'pullback'

                        if not passes_price_action:
                            continue  # Stock failed Price Action filter

                    # Stock passed all filters - add to results
                    self.task.matched_stocks += 1
                    # Commit immediately to persist matched_stocks count (prevents loss on refresh)
                    db.session.commit()

                    # Calculate scan score for ranking
                    scan_score = self._calculate_scan_score(stock, criteria, ma_above, price_action_pattern)

                    # Store result data (will be saved in batch)
                    matched_results.append({
                        'stock': stock,
                        'current_price': current_price,
                        'ma_above': ma_above,
                        'price_action_pattern': price_action_pattern,
                        'scan_score': scan_score
                    })

                    # Bulk insert every 50 results
                    if len(matched_results) >= 50:
                        self._save_results_batch(matched_results)
                        matched_results = []

                except Exception as e:
                    self.task.failed_stocks += 1
                    error_msg = f'Error scanning {stock.tradingsymbol}: {str(e)}'
                    current_app.logger.error(
                        f'Scanner task {self.task_id}: {error_msg}',
                        exc_info=True
                    )

            # Save any remaining results
            if matched_results:
                self._save_results_batch(matched_results)

            # Assign rankings based on scan scores
            self.task.progress_message = 'Finalizing results and calculating rankings...'
            db.session.commit()
            self._assign_rankings()

            # Mark task as completed
            self.task.status = 'completed'
            self.task.completed_at = datetime.utcnow()
            self.task.current_stock_symbol = None
            self.task.progress_message = f'Scan completed: {self.task.matched_stocks} stocks matched'
            db.session.commit()

            current_app.logger.info(
                f'Scanner task {self.task_id}: Completed - '
                f'Scanned: {self.task.scanned_stocks}, '
                f'Matched: {self.task.matched_stocks}, '
                f'Failed: {self.task.failed_stocks}'
            )

        except Exception as e:
            # Handle unexpected errors
            self.task.status = 'failed'
            self.task.error_message = str(e)
            self.task.completed_at = datetime.utcnow()
            db.session.commit()
            current_app.logger.error(f'Scanner task {self.task_id}: Fatal error - {str(e)}', exc_info=True)
            raise

    def _get_stocks_to_scan(self) -> List[Instrument]:
        """
        Get stocks to scan based on profile criteria

        Returns:
            List of Instrument objects matching criteria
        """
        # Get profile
        profile = self.task.profile
        if not profile or not profile.criteria:
            # No criteria, scan all NIFTY 500 stocks
            current_app.logger.info(f'Scanner task {self.task_id}: No criteria, scanning all NIFTY 500')
            return Instrument.query.filter_by(
                exchange='NSE',
                instrument_type='EQ',
                is_nifty500=True
            ).all()

        # Parse criteria
        try:
            criteria = json.loads(profile.criteria)
        except json.JSONDecodeError:
            current_app.logger.warning(f'Scanner task {self.task_id}: Invalid criteria JSON, scanning all NIFTY 500')
            return Instrument.query.filter_by(
                exchange='NSE',
                instrument_type='EQ',
                is_nifty500=True
            ).all()

        scan_level = criteria.get('scan_level', 'subsector')
        selected_stages = criteria.get('selected_stages', [])
        selected_sectors = criteria.get('selected_sectors', [])
        selected_subsectors = criteria.get('selected_subsectors', [])

        # Get enable/disable flags
        enable_scan_level_filter = criteria.get('enable_scan_level_filter', True)
        enable_rs_filter = criteria.get('enable_rs_filter', False)
        enable_volume_contraction_filter = criteria.get('enable_volume_contraction_filter', False)
        enable_ma_filter = criteria.get('enable_ma_filter', False)

        # Get RS filter values
        rs_sub_min = criteria.get('rs_sub_min')
        rs_sub_max = criteria.get('rs_sub_max')
        rs_sec_min = criteria.get('rs_sec_min')
        rs_sec_max = criteria.get('rs_sec_max')

        # Get Volume Contraction filter values
        selected_volume_status = criteria.get('selected_volume_status', [])
        selected_volume_classification = criteria.get('selected_volume_classification', [])

        # Get MA filter values
        selected_sma = criteria.get('selected_sma', [])
        selected_ema = criteria.get('selected_ema', [])

        current_app.logger.info(
            f'Scanner task {self.task_id}: Criteria - Level: {scan_level}, '
            f'Stages: {selected_stages}, Sectors: {selected_sectors}, Subsectors: {selected_subsectors}, '
            f'Enable Scan Level Filter: {enable_scan_level_filter}, Enable RS Filter: {enable_rs_filter}, '
            f'RS Sub: [{rs_sub_min}, {rs_sub_max}], RS Sec: [{rs_sec_min}, {rs_sec_max}], '
            f'Enable Volume Contraction Filter: {enable_volume_contraction_filter}, '
            f'Volume Status: {selected_volume_status}, Volume Classification: {selected_volume_classification}'
        )

        # Build query based on scan level (only if scan level filter is enabled)
        query = Instrument.query.filter_by(
            exchange='NSE',
            instrument_type='EQ',
            is_nifty500=True
        )

        if enable_scan_level_filter:
            if scan_level == 'stage' and selected_stages:
                # Filter by selected stages
                # Important: Stock, subsector, AND sector stages must ALL match selected stages
                # Join with SubSector and Sector to check all three stages
                from app.models import Sector
                query = query.join(SubSector, Instrument.sub_sector_id == SubSector.id).join(
                    Sector, SubSector.sector_id == Sector.id
                ).filter(
                    Instrument.current_stage.in_(selected_stages),
                    SubSector.current_stage.in_(selected_stages),
                    Sector.current_stage.in_(selected_stages)
                )
            elif scan_level == 'sector' and selected_sectors:
                # Filter by selected sectors (via subsector relationship)
                query = query.join(SubSector, Instrument.sub_sector_id == SubSector.id).filter(
                    SubSector.sector_id.in_(selected_sectors)
                )
                # For sector-level scan, ALWAYS filter by stock stages
                # If no stages selected, default to stages 1 and 2 (Accumulation and Markup)
                if not selected_stages:
                    selected_stages = [1, 2]
                    current_app.logger.info(f'Scanner task {self.task_id}: No stages selected for sector-level scan, defaulting to stages {selected_stages}')
                query = query.filter(Instrument.current_stage.in_(selected_stages))
                current_app.logger.info(f'Scanner task {self.task_id}: Applied stock stage filter {selected_stages} to sector-level scan')
            elif scan_level == 'subsector' and selected_subsectors:
                # Filter by selected subsectors
                query = query.filter(
                    Instrument.sub_sector_id.in_(selected_subsectors)
                )
                # For subsector-level scan, ALWAYS filter by stock stages
                # If no stages selected, default to stages 1 and 2 (Accumulation and Markup)
                if not selected_stages:
                    selected_stages = [1, 2]
                    current_app.logger.info(f'Scanner task {self.task_id}: No stages selected for subsector-level scan, defaulting to stages {selected_stages}')
                query = query.filter(Instrument.current_stage.in_(selected_stages))
                current_app.logger.info(f'Scanner task {self.task_id}: Applied stock stage filter {selected_stages} to subsector-level scan')
            else:
                # No valid selections, log warning but continue
                current_app.logger.warning(f'Scanner task {self.task_id}: No valid selections in scan level criteria')

        # Apply RS filters (only if RS filter is enabled)
        if enable_rs_filter:
            # Filter by RS vs Subsector
            if rs_sub_min is not None:
                query = query.filter(Instrument.rs_vs_subsector.isnot(None))
                query = query.filter(Instrument.rs_vs_subsector >= rs_sub_min)
                current_app.logger.info(f'Scanner task {self.task_id}: Applying RS Sub Min filter: >= {rs_sub_min}')
            if rs_sub_max is not None:
                query = query.filter(Instrument.rs_vs_subsector.isnot(None))
                query = query.filter(Instrument.rs_vs_subsector <= rs_sub_max)
                current_app.logger.info(f'Scanner task {self.task_id}: Applying RS Sub Max filter: <= {rs_sub_max}')

            # Filter by RS vs Sector
            if rs_sec_min is not None:
                query = query.filter(Instrument.rs_vs_sector.isnot(None))
                query = query.filter(Instrument.rs_vs_sector >= rs_sec_min)
                current_app.logger.info(f'Scanner task {self.task_id}: Applying RS Sec Min filter: >= {rs_sec_min}')
            if rs_sec_max is not None:
                query = query.filter(Instrument.rs_vs_sector.isnot(None))
                query = query.filter(Instrument.rs_vs_sector <= rs_sec_max)
                current_app.logger.info(f'Scanner task {self.task_id}: Applying RS Sec Max filter: <= {rs_sec_max}')

        # Apply Volume Contraction filters (only if volume contraction filter is enabled)
        if enable_volume_contraction_filter:
            # Filter by Volume Dry-Up Status
            if selected_volume_status:
                query = query.filter(Instrument.volume_dryup_status.in_(selected_volume_status))
                current_app.logger.info(
                    f'Scanner task {self.task_id}: Applying Volume Status filter: {selected_volume_status}'
                )

            # Filter by Volume Dry-Up Classification
            if selected_volume_classification:
                query = query.filter(Instrument.volume_dryup_classification.in_(selected_volume_classification))
                current_app.logger.info(
                    f'Scanner task {self.task_id}: Applying Volume Classification filter: {selected_volume_classification}'
                )

            # Exclude stocks with NULL volume dry-up data when volume contraction filter is enabled
            if selected_volume_status:
                query = query.filter(Instrument.volume_dryup_status.isnot(None))
            if selected_volume_classification:
                query = query.filter(Instrument.volume_dryup_classification.isnot(None))

        # Note: MA filter is NOT applied here - it runs in the main loop (Step 4)
        # This ensures proper sequential filter order:
        # 1. Stage/Sector → 2. RS → 3. Volume → 4. MA → 5. Price Action

        stocks = query.all()
        current_app.logger.info(f'Scanner task {self.task_id}: Filtered to {len(stocks)} stocks')

        return stocks

    def _is_breakout_pattern(self, candles, lookback_days):
        """
        Detect breakout pattern (from scanner_routes.py logic)
        """
        try:
            lookback_candles = candles[-lookback_days:]
            if len(lookback_candles) < 20:
                return False

            current_price = lookback_candles[-1]['close']
            resistance_high = max(c['high'] for c in lookback_candles[:-5])
            recent_candles = lookback_candles[-5:]

            # Check if any recent candle broke above resistance
            breakout_detected = any(c['high'] > resistance_high * 1.01 for c in recent_candles)
            if not breakout_detected:
                return False

            # Verify sustained breakout
            if current_price < resistance_high * 0.98:
                return False

            # Volume confirmation
            avg_volume = sum(c['volume'] for c in lookback_candles[:-5]) / (len(lookback_candles) - 5)
            recent_volume = sum(c['volume'] for c in recent_candles) / len(recent_candles)

            return recent_volume >= avg_volume * 1.2

        except Exception:
            return False

    def _is_pullback_pattern(self, candles, lookback_days):
        """
        Detect pullback pattern (from scanner_routes.py logic)
        """
        try:
            lookback_candles = candles[-lookback_days:]
            if len(lookback_candles) < 30:
                return False

            current_price = lookback_candles[-1]['close']
            recent_high_period = lookback_candles[-30:]
            recent_high = max(c['high'] for c in recent_high_period)

            # Calculate pullback percentage
            pullback_pct = ((recent_high - current_price) / recent_high) * 100

            # Check healthy range (5-25%)
            if pullback_pct < 5 or pullback_pct > 25:
                return False

            # Check if above 50-day MA
            if len(lookback_candles) >= 50:
                ma_50 = sum(c['close'] for c in lookback_candles[-50:]) / 50
                if current_price < ma_50 * 0.95:
                    return False

            # Check decreasing volume
            recent_10_days = lookback_candles[-10:]
            prev_10_days = lookback_candles[-20:-10]

            recent_avg_volume = sum(c['volume'] for c in recent_10_days) / 10
            prev_avg_volume = sum(c['volume'] for c in prev_10_days) / 10

            return recent_avg_volume <= prev_avg_volume * 1.1

        except Exception:
            return False

    def _calculate_scan_score(self, stock, criteria, ma_above, price_action_pattern):
        """
        Calculate scan score based on multiple factors for ranking

        Scoring algorithm:
        - Stage 2 = +50 points (ideal stage)
        - Stage 1 = +30 points (accumulation)
        - RS Score = (RS_subsector * 0.6 + RS_sector * 0.4)
        - Volume Dry Up = +10 points
        - Price Action Pattern = +5 points
        - Above MAs = +2 points per MA
        """
        score = 0.0

        # Stage scoring
        if stock.current_stage == 2:
            score += 50
        elif stock.current_stage == 1:
            score += 30
        elif stock.current_stage == 3:
            score += 10

        # RS scoring (weighted average)
        rs_subsector = stock.rs_vs_subsector or 50
        rs_sector = stock.rs_vs_sector or 50
        score += (rs_subsector * 0.6 + rs_sector * 0.4)

        # Volume dry up bonus
        if stock.volume_dryup_status == 'dry_up':
            score += 10

        # Price action pattern bonus
        if price_action_pattern:
            score += 5

        # Moving average bonus
        score += len(ma_above) * 2

        return round(score, 2)

    def _save_results_batch(self, matched_results):
        """
        Save a batch of matched stock results to database
        """
        try:
            for result_data in matched_results:
                stock = result_data['stock']

                # Create ScanResultStock record
                result = ScanResultStock(
                    task_id=self.task_id,
                    instrument_id=stock.id,
                    tradingsymbol=stock.tradingsymbol,
                    current_price=result_data['current_price'],
                    stage=stock.current_stage,
                    sector_name=stock.sector,  # Already a string
                    subsector_name=stock.sub_sector,  # Already a string
                    rs_vs_subsector=stock.rs_vs_subsector,
                    rs_vs_sector=stock.rs_vs_sector,
                    volume_dryup_status=stock.volume_dryup_status,
                    volume_dryup_classification=stock.volume_dryup_classification,
                    volume_ratio_pct=stock.volume_ratio_pct,
                    ma_above=json.dumps(result_data['ma_above']),
                    price_action_pattern=result_data['price_action_pattern'],
                    scan_score=result_data['scan_score'],
                    scan_rank=0  # Will be assigned later in _assign_rankings
                )
                db.session.add(result)

            db.session.commit()
            current_app.logger.info(f'Scanner task {self.task_id}: Saved batch of {len(matched_results)} results')

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Scanner task {self.task_id}: Error saving results batch - {str(e)}', exc_info=True)
            raise

    def _assign_rankings(self):
        """
        Assign rankings to results based on scan scores (highest score = rank 1)
        """
        try:
            # Get all results for this task, ordered by score descending
            results = ScanResultStock.query.filter_by(task_id=self.task_id).order_by(
                ScanResultStock.scan_score.desc()
            ).all()

            # Assign rankings
            for rank, result in enumerate(results, start=1):
                result.scan_rank = rank

            db.session.commit()
            current_app.logger.info(f'Scanner task {self.task_id}: Assigned rankings to {len(results)} results')

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Scanner task {self.task_id}: Error assigning rankings - {str(e)}', exc_info=True)
            raise


# Profile Management Functions

def get_user_profiles(user_id: int) -> List[ScannerProfile]:
    """Get all scanner profiles for a user"""
    try:
        return ScannerProfile.query.filter_by(user_id=user_id).order_by(
            ScannerProfile.is_default.desc(),
            ScannerProfile.created_at.desc()
        ).all()
    except Exception as e:
        current_app.logger.error(f'Error getting user profiles: {str(e)}', exc_info=True)
        return []


def get_default_profile(user_id: int) -> Optional[ScannerProfile]:
    """Get user's default scanner profile"""
    try:
        return ScannerProfile.query.filter_by(
            user_id=user_id,
            is_default=True
        ).first()
    except Exception as e:
        current_app.logger.error(f'Error getting default profile: {str(e)}', exc_info=True)
        return None


def set_default_profile(user_id: int, profile_id: int) -> bool:
    """Set a profile as the default for a user"""
    try:
        # Unset all defaults for this user
        ScannerProfile.query.filter_by(
            user_id=user_id,
            is_default=True
        ).update({'is_default': False})

        # Set new default
        profile = ScannerProfile.query.filter_by(
            id=profile_id,
            user_id=user_id
        ).first()

        if profile:
            profile.is_default = True
            db.session.commit()
            return True

        return False

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error setting default profile: {str(e)}', exc_info=True)
        return False


def delete_profile(user_id: int, profile_id: int) -> bool:
    """Delete a scanner profile"""
    try:
        profile = ScannerProfile.query.filter_by(
            id=profile_id,
            user_id=user_id
        ).first()

        if profile:
            db.session.delete(profile)
            db.session.commit()
            return True

        return False

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting profile: {str(e)}', exc_info=True)
        return False
