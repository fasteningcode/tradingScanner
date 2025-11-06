"""
Historical Index Service
Calculates and stores historical indices for sectors and subsectors using historical candlestick data.
"""
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Tuple
from sqlalchemy import func
from app import db
from app.models import (
    Sector, SubSector, Instrument, HistoricalData,
    StockInformation, IndexHistory
)
import json
import logging

logger = logging.getLogger(__name__)

# Base date for index calculation (July 1, 2025 = 1000)
BASE_DATE = date(2025, 7, 1)
BASE_INDEX_VALUE = 1000.0


class HistoricalIndexService:
    """Service for calculating historical indices"""

    @staticmethod
    def calculate_free_float_market_cap_for_date(
        instruments: List[Instrument],
        target_date: date
    ) -> Tuple[Dict[str, float], List[str]]:
        """
        Calculate free-float market cap for each stock on a specific date.

        Args:
            instruments: List of Instrument objects
            target_date: Date to calculate market cap for

        Returns:
            Tuple of (market_caps dict, warnings list)
            - market_caps: Dict mapping tradingsymbol to free-float market cap
            - warnings: List of warning messages for stocks that couldn't be calculated
        """
        result = {}
        warnings = []
        target_date_str = target_date.isoformat()

        for instrument in instruments:
            try:
                # Get historical data for this instrument (day interval)
                hist_data = HistoricalData.query.filter_by(
                    tradingsymbol=instrument.tradingsymbol,
                    interval='day'
                ).first()

                if not hist_data:
                    msg = f"No historical data for {instrument.tradingsymbol}"
                    logger.warning(msg)
                    warnings.append(msg)
                    continue

                # Parse candlestick data
                candles = hist_data.get_candles()
                if not candles:
                    msg = f"No candles for {instrument.tradingsymbol}"
                    logger.warning(msg)
                    warnings.append(msg)
                    continue

                # Find the candle for target date
                # Normalize both dates to handle different formats
                target_candle = None
                for candle in candles:
                    candle_date_str = candle.get('date', '')
                    # Try to parse and compare dates properly
                    try:
                        # If candle date is in different format, normalize it
                        if 'T' in candle_date_str:
                            # ISO format with time: "2025-07-01T00:00:00"
                            candle_date_str = candle_date_str.split('T')[0]

                        if candle_date_str == target_date_str:
                            target_candle = candle
                            break
                    except Exception as e:
                        logger.warning(f"Error parsing candle date {candle_date_str}: {str(e)}")
                        continue

                if not target_candle:
                    msg = f"No candle for {instrument.tradingsymbol} on {target_date_str}"
                    logger.warning(msg)
                    warnings.append(msg)
                    continue

                close_price = target_candle.get('close')
                if close_price is None:
                    msg = f"No close price for {instrument.tradingsymbol} on {target_date_str}"
                    logger.warning(msg)
                    warnings.append(msg)
                    continue

                # Get float shares from stock_information
                stock_info = StockInformation.query.filter_by(
                    tradingsymbol=instrument.tradingsymbol
                ).first()

                if not stock_info or not stock_info.float_shares:
                    msg = f"No float_shares for {instrument.tradingsymbol}"
                    logger.warning(msg)
                    warnings.append(msg)
                    continue

                # Calculate free-float market cap = close × float_shares
                # Stock price is per share, float_shares is total count
                # Result should be in crores (assuming close is in INR and we divide by 10^7)
                free_float_mc = (close_price * stock_info.float_shares) / 10000000.0
                result[instrument.tradingsymbol] = free_float_mc

            except Exception as e:
                msg = f"Error calculating market cap for {instrument.tradingsymbol}: {str(e)}"
                logger.error(msg)
                warnings.append(msg)
                continue

        return result, warnings

    @staticmethod
    def calculate_base_market_cap(
        sector_id: Optional[int] = None,
        subsector_id: Optional[int] = None
    ) -> Optional[float]:
        """
        Calculate the base free-float market cap sum for July 1, 2025.

        Args:
            sector_id: Sector ID (for sector index)
            subsector_id: SubSector ID (for subsector index)

        Returns:
            Base market cap sum (SFFMS) or None if calculation fails
        """
        try:
            # Get instruments based on sector or subsector
            if subsector_id:
                instruments = Instrument.query.filter_by(
                    sub_sector_id=subsector_id,
                    is_nifty500=True
                ).all()
            elif sector_id:
                instruments = Instrument.query.join(SubSector).filter(
                    SubSector.sector_id == sector_id,
                    SubSector.is_active == True,
                    Instrument.is_nifty500 == True
                ).all()
            else:
                # Market index - all NIFTY 500 stocks
                instruments = Instrument.query.filter_by(is_nifty500=True).all()

            if not instruments:
                logger.error(f"No instruments found for sector={sector_id}, subsector={subsector_id}")
                return None

            # Calculate free-float market caps for base date
            market_caps, warnings = HistoricalIndexService.calculate_free_float_market_cap_for_date(
                instruments, BASE_DATE
            )

            if not market_caps:
                logger.error(f"No market caps calculated for base date {BASE_DATE}")
                if warnings:
                    logger.error(f"Warnings: {len(warnings)} stocks had issues")
                return None

            # Sum all free-float market caps
            base_sffms = sum(market_caps.values())
            if warnings:
                logger.warning(f"Base SFFMS calculation had {len(warnings)} warnings")

            logger.info(f"Base SFFMS for sector={sector_id}, subsector={subsector_id}: {base_sffms:.2f} Cr")
            return base_sffms

        except Exception as e:
            logger.error(f"Error calculating base market cap: {str(e)}")
            return None

    @staticmethod
    def calculate_index_for_date(
        target_date: date,
        sector_id: Optional[int] = None,
        subsector_id: Optional[int] = None,
        base_sffms: Optional[float] = None
    ) -> Optional[float]:
        """
        Calculate index value for a specific date.

        Formula: Index = (SFFMS / Base_SFFMS) × 1000

        Args:
            target_date: Date to calculate index for
            sector_id: Sector ID (for sector index)
            subsector_id: SubSector ID (for subsector index)
            base_sffms: Pre-calculated base SFFMS (if None, will calculate)

        Returns:
            Index value or None if calculation fails
        """
        try:
            # Calculate base SFFMS if not provided
            if base_sffms is None:
                base_sffms = HistoricalIndexService.calculate_base_market_cap(
                    sector_id=sector_id,
                    subsector_id=subsector_id
                )
                if base_sffms is None:
                    return None

            # Get instruments
            if subsector_id:
                instruments = Instrument.query.filter_by(
                    sub_sector_id=subsector_id,
                    is_nifty500=True
                ).all()
            elif sector_id:
                instruments = Instrument.query.join(SubSector).filter(
                    SubSector.sector_id == sector_id,
                    SubSector.is_active == True,
                    Instrument.is_nifty500 == True
                ).all()
            else:
                instruments = Instrument.query.filter_by(is_nifty500=True).all()

            # Calculate free-float market caps for target date
            market_caps, warnings = HistoricalIndexService.calculate_free_float_market_cap_for_date(
                instruments, target_date
            )

            if not market_caps:
                logger.warning(f"No market caps calculated for {target_date}")
                return None

            if warnings:
                logger.debug(f"{len(warnings)} stocks had issues on {target_date}")

            # Sum all free-float market caps
            target_sffms = sum(market_caps.values())

            # Calculate index = (SFFMS / Base_SFFMS) × 1000
            index_value = (target_sffms / base_sffms) * BASE_INDEX_VALUE

            logger.info(f"Index for {target_date}: {index_value:.2f} (SFFMS={target_sffms:.2f})")
            return index_value

        except Exception as e:
            logger.error(f"Error calculating index for {target_date}: {str(e)}")
            return None

    @staticmethod
    def generate_index_history(
        index_symbol: str,
        start_date: date,
        end_date: date,
        sector_id: Optional[int] = None,
        subsector_id: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Generate historical index values for a date range and store in database.

        Args:
            index_symbol: Index symbol (max 10 chars)
            start_date: Start date for calculation
            end_date: End date for calculation
            sector_id: Sector ID (for sector index)
            subsector_id: SubSector ID (for subsector index)

        Returns:
            Dict with status and statistics
        """
        try:
            logger.info(f"Generating index history for {index_symbol} from {start_date} to {end_date}")

            # Calculate base SFFMS once
            base_sffms = HistoricalIndexService.calculate_base_market_cap(
                sector_id=sector_id,
                subsector_id=subsector_id
            )

            if base_sffms is None:
                return {
                    'success': False,
                    'error': 'Failed to calculate base market cap',
                    'dates_processed': 0
                }

            # Generate list of dates to process
            current_date = start_date
            dates_to_process = []
            while current_date <= end_date:
                dates_to_process.append(current_date)
                current_date += timedelta(days=1)

            # Calculate and store indices
            success_count = 0
            skip_count = 0
            error_count = 0
            error_details = []

            # Process in batches with proper transaction handling
            batch_size = 50
            batch_records = []

            for target_date in dates_to_process:
                try:
                    # Check if index already exists
                    existing = IndexHistory.query.filter_by(
                        index_symbol=index_symbol,
                        date=target_date
                    ).first()

                    if existing:
                        logger.debug(f"Index for {index_symbol} on {target_date} already exists")
                        skip_count += 1
                        continue

                    # Calculate index value
                    index_value = HistoricalIndexService.calculate_index_for_date(
                        target_date,
                        sector_id=sector_id,
                        subsector_id=subsector_id,
                        base_sffms=base_sffms
                    )

                    if index_value is None:
                        error_msg = f"Failed to calculate index for {target_date}"
                        logger.warning(error_msg)
                        error_count += 1
                        error_details.append(error_msg)
                        continue

                    # Store in database
                    index_history = IndexHistory(
                        index_symbol=index_symbol,
                        date=target_date,
                        index_value=index_value,
                        index_calculated_date=datetime.utcnow()
                    )
                    batch_records.append(index_history)

                    # Commit in batches with proper transaction handling
                    if len(batch_records) >= batch_size:
                        try:
                            for record in batch_records:
                                db.session.add(record)
                            db.session.commit()
                            success_count += len(batch_records)
                            logger.info(f"Progress: {success_count} indices calculated")
                            batch_records = []
                        except Exception as batch_error:
                            db.session.rollback()
                            error_msg = f"Batch commit failed: {str(batch_error)}"
                            logger.error(error_msg)
                            error_details.append(error_msg)
                            error_count += len(batch_records)
                            batch_records = []

                except Exception as e:
                    error_msg = f"Error processing {target_date}: {str(e)}"
                    logger.error(error_msg)
                    error_details.append(error_msg)
                    error_count += 1
                    continue

            # Final commit for remaining records
            if batch_records:
                try:
                    for record in batch_records:
                        db.session.add(record)
                    db.session.commit()
                    success_count += len(batch_records)
                    logger.info(f"Final batch: {len(batch_records)} indices committed")
                except Exception as batch_error:
                    db.session.rollback()
                    error_msg = f"Final batch commit failed: {str(batch_error)}"
                    logger.error(error_msg)
                    error_details.append(error_msg)
                    error_count += len(batch_records)

            logger.info(f"Index generation complete: {success_count} success, {skip_count} skipped, {error_count} errors")

            return {
                'success': True,
                'dates_processed': len(dates_to_process),
                'success_count': success_count,
                'skip_count': skip_count,
                'error_count': error_count,
                'error_details': error_details[:10] if error_details else []  # Return first 10 errors
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error generating index history: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'dates_processed': 0
            }

    @staticmethod
    def generate_all_indices(
        start_date: date,
        end_date: date
    ) -> Dict[str, any]:
        """
        Generate historical indices for all sectors and subsectors.

        Args:
            start_date: Start date for calculation
            end_date: End date for calculation

        Returns:
            Dict with status and statistics
        """
        try:
            logger.info(f"Generating all indices from {start_date} to {end_date}")
            results = {
                'market': None,
                'sectors': {},
                'subsectors': {}
            }

            # Generate market index (NIFTY 500 Custom)
            logger.info("Generating market index...")
            market_result = HistoricalIndexService.generate_index_history(
                index_symbol='NIFTY500',
                start_date=start_date,
                end_date=end_date
            )
            results['market'] = market_result

            # Generate sector indices
            sectors = Sector.query.filter_by(is_active=True).all()
            for sector in sectors:
                if not sector.index_symbol:
                    logger.warning(f"Sector {sector.name} has no index_symbol, skipping")
                    continue

                logger.info(f"Generating index for sector: {sector.name} ({sector.index_symbol})")
                sector_result = HistoricalIndexService.generate_index_history(
                    index_symbol=sector.index_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    sector_id=sector.id
                )
                results['sectors'][sector.index_symbol] = sector_result

            # Generate subsector indices
            subsectors = SubSector.query.filter_by(is_active=True).all()
            for subsector in subsectors:
                if not subsector.index_symbol:
                    logger.warning(f"SubSector {subsector.name} has no index_symbol, skipping")
                    continue

                logger.info(f"Generating index for subsector: {subsector.name} ({subsector.index_symbol})")
                subsector_result = HistoricalIndexService.generate_index_history(
                    index_symbol=subsector.index_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    subsector_id=subsector.id
                )
                results['subsectors'][subsector.index_symbol] = subsector_result

            return {
                'success': True,
                'results': results
            }

        except Exception as e:
            logger.error(f"Error generating all indices: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def clear_index_history(
        index_symbol: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Clear index history data.

        Args:
            index_symbol: If provided, clear only this index. If None, clear all.

        Returns:
            Dict with status and count of deleted records
        """
        try:
            if index_symbol:
                deleted = IndexHistory.query.filter_by(index_symbol=index_symbol).delete()
                logger.info(f"Deleted {deleted} records for {index_symbol}")
            else:
                deleted = IndexHistory.query.delete()
                logger.info(f"Deleted {deleted} total index history records")

            db.session.commit()

            return {
                'success': True,
                'deleted_count': deleted
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error clearing index history: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'deleted_count': 0
            }

    @staticmethod
    def get_latest_index_value(
        index_symbol: str,
        as_of_date: Optional[date] = None
    ) -> Optional[float]:
        """
        Get the latest index value for an index symbol.

        Args:
            index_symbol: Index symbol to look up
            as_of_date: Get value as of this date (if None, get latest)

        Returns:
            Index value or None if not found
        """
        try:
            query = IndexHistory.query.filter_by(index_symbol=index_symbol)

            if as_of_date:
                query = query.filter(IndexHistory.date <= as_of_date)

            latest = query.order_by(IndexHistory.date.desc()).first()

            return latest.index_value if latest else None

        except Exception as e:
            logger.error(f"Error getting latest index value: {str(e)}")
            return None

    @staticmethod
    def get_index_with_change(
        index_symbol: str,
        as_of_date: Optional[date] = None
    ) -> Optional[Dict[str, any]]:
        """
        Get the latest index value with percentage change vs previous trading day.

        Args:
            index_symbol: Index symbol to look up
            as_of_date: Get value as of this date (if None, get latest)

        Returns:
            Dict with index_value, previous_value, percentage_change, date, change_direction
            or None if not found
        """
        try:
            # Get latest index record
            query = IndexHistory.query.filter_by(index_symbol=index_symbol)

            if as_of_date:
                query = query.filter(IndexHistory.date <= as_of_date)

            latest = query.order_by(IndexHistory.date.desc()).first()

            if not latest:
                logger.warning(f"No index history found for {index_symbol}")
                return None

            # Get previous trading day's value
            previous = IndexHistory.query.filter_by(
                index_symbol=index_symbol
            ).filter(
                IndexHistory.date < latest.date
            ).order_by(IndexHistory.date.desc()).first()

            # Calculate percentage change
            percentage_change = None
            change_direction = 'neutral'
            previous_value = None

            if previous and previous.index_value:
                previous_value = previous.index_value
                if previous_value != 0:
                    percentage_change = ((latest.index_value - previous_value) / previous_value) * 100

                    if percentage_change > 0:
                        change_direction = 'up'
                    elif percentage_change < 0:
                        change_direction = 'down'

            return {
                'index_symbol': index_symbol,
                'index_value': latest.index_value,
                'date': latest.date,
                'previous_value': previous_value,
                'previous_date': previous.date if previous else None,
                'percentage_change': percentage_change,
                'change_direction': change_direction,
                'calculated_at': latest.index_calculated_date
            }

        except Exception as e:
            logger.error(f"Error getting index with change for {index_symbol}: {str(e)}")
            return None
