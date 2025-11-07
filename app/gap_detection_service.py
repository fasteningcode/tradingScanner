"""
Gap Detection Service

This module provides functionality to detect missing historical data (gaps)
in the database and identify which stocks/dates need synchronization.
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple, Set
from flask import current_app
from app import db
from app.models import HistoricalData, Instrument
from sqlalchemy import and_


class GapDetectionService:
    """Service for detecting gaps in historical data"""

    @staticmethod
    def get_last_synced_date(tradingsymbol: str, interval: str = 'day') -> Optional[date]:
        """
        Get the most recent date for which historical data exists for a stock.

        Args:
            tradingsymbol: Trading symbol of the instrument
            interval: Candle interval (default: 'day')

        Returns:
            Date of the most recent candle, or None if no data exists
        """
        try:
            # Query the HistoricalData table
            historical_data = HistoricalData.query.filter_by(
                tradingsymbol=tradingsymbol,
                interval=interval
            ).first()

            if not historical_data:
                current_app.logger.debug(f"No historical data found for {tradingsymbol}")
                return None

            # Get candles and find the maximum date
            candles = historical_data.get_candles()
            if not candles:
                current_app.logger.debug(f"No candles in historical data for {tradingsymbol}")
                return None

            # Find the most recent date
            max_date_str = max(candle['date'] for candle in candles)

            # Parse the date string (format: "YYYY-MM-DD")
            if isinstance(max_date_str, str):
                max_date = datetime.strptime(max_date_str, '%Y-%m-%d').date()
            else:
                max_date = max_date_str

            current_app.logger.debug(f"Last synced date for {tradingsymbol}: {max_date}")
            return max_date

        except Exception as e:
            current_app.logger.error(f"Error getting last synced date for {tradingsymbol}: {str(e)}")
            return None

    @staticmethod
    def find_missing_dates(
        tradingsymbol: str,
        from_date: date,
        to_date: date,
        interval: str = 'day'
    ) -> List[date]:
        """
        Find dates that are missing in historical data for a specific stock.

        Args:
            tradingsymbol: Trading symbol of the instrument
            from_date: Start date of the range to check
            to_date: End date of the range to check
            interval: Candle interval (default: 'day')

        Returns:
            List of dates that are missing (no candle data exists)
        """
        try:
            # Query the HistoricalData table
            historical_data = HistoricalData.query.filter_by(
                tradingsymbol=tradingsymbol,
                interval=interval
            ).first()

            # If no historical data exists, all dates in range are missing
            if not historical_data:
                # Generate all dates in the range
                missing_dates = []
                current_date = from_date
                while current_date <= to_date:
                    missing_dates.append(current_date)
                    current_date += timedelta(days=1)
                current_app.logger.debug(
                    f"No historical data for {tradingsymbol}, all {len(missing_dates)} dates are missing"
                )
                return missing_dates

            # Get existing candles
            candles = historical_data.get_candles()
            if not candles:
                missing_dates = []
                current_date = from_date
                while current_date <= to_date:
                    missing_dates.append(current_date)
                    current_date += timedelta(days=1)
                return missing_dates

            # Create a set of existing dates for fast lookup
            existing_dates = set()
            for candle in candles:
                candle_date_str = candle['date']
                if isinstance(candle_date_str, str):
                    candle_date = datetime.strptime(candle_date_str, '%Y-%m-%d').date()
                else:
                    candle_date = candle_date_str
                existing_dates.add(candle_date)

            # Find missing dates in the range
            missing_dates = []
            current_date = from_date
            while current_date <= to_date:
                if current_date not in existing_dates:
                    missing_dates.append(current_date)
                current_date += timedelta(days=1)

            current_app.logger.debug(
                f"Found {len(missing_dates)} missing dates for {tradingsymbol} "
                f"between {from_date} and {to_date}"
            )
            return missing_dates

        except Exception as e:
            current_app.logger.error(
                f"Error finding missing dates for {tradingsymbol}: {str(e)}"
            )
            return []

    @staticmethod
    def get_stocks_needing_sync(
        target_date: date,
        interval: str = 'day',
        only_nifty500: bool = True
    ) -> List[str]:
        """
        Find stocks that are missing data for a specific date.

        Args:
            target_date: The date to check for
            interval: Candle interval (default: 'day')
            only_nifty500: If True, only check NIFTY 500 stocks (default: True)

        Returns:
            List of trading symbols that need synchronization for the target date
        """
        try:
            # Get list of instruments to check
            query = Instrument.query.filter_by(
                exchange='NSE',
                instrument_type='EQ'
            )

            if only_nifty500:
                query = query.filter_by(is_nifty500=True)

            instruments = query.all()

            stocks_needing_sync = []

            for instrument in instruments:
                # Check if this stock has data for the target date
                missing_dates = GapDetectionService.find_missing_dates(
                    instrument.tradingsymbol,
                    target_date,
                    target_date,
                    interval
                )

                if missing_dates:
                    stocks_needing_sync.append(instrument.tradingsymbol)

            current_app.logger.info(
                f"Found {len(stocks_needing_sync)} stocks needing sync for {target_date}"
            )
            return stocks_needing_sync

        except Exception as e:
            current_app.logger.error(
                f"Error getting stocks needing sync for {target_date}: {str(e)}"
            )
            return []

    @staticmethod
    def analyze_coverage(
        from_date: date,
        to_date: date,
        interval: str = 'day',
        only_nifty500: bool = True
    ) -> Dict[str, any]:
        """
        Analyze data coverage across all stocks for a date range.

        Args:
            from_date: Start date of analysis
            to_date: End date of analysis
            interval: Candle interval (default: 'day')
            only_nifty500: If True, only analyze NIFTY 500 stocks (default: True)

        Returns:
            Dictionary containing coverage statistics
        """
        try:
            # Get list of instruments to analyze
            query = Instrument.query.filter_by(
                exchange='NSE',
                instrument_type='EQ'
            )

            if only_nifty500:
                query = query.filter_by(is_nifty500=True)

            instruments = query.all()
            total_stocks = len(instruments)

            # Calculate total expected dates
            date_count = (to_date - from_date).days + 1
            expected_total = total_stocks * date_count

            # Statistics
            stocks_with_complete_data = 0
            stocks_with_partial_data = 0
            stocks_with_no_data = 0
            total_missing_candles = 0
            stocks_by_missing_count = {}

            for instrument in instruments:
                missing_dates = GapDetectionService.find_missing_dates(
                    instrument.tradingsymbol,
                    from_date,
                    to_date,
                    interval
                )

                missing_count = len(missing_dates)
                total_missing_candles += missing_count

                if missing_count == 0:
                    stocks_with_complete_data += 1
                elif missing_count == date_count:
                    stocks_with_no_data += 1
                else:
                    stocks_with_partial_data += 1

                # Track stocks by missing count for detailed analysis
                if missing_count > 0:
                    if missing_count not in stocks_by_missing_count:
                        stocks_by_missing_count[missing_count] = []
                    stocks_by_missing_count[missing_count].append(instrument.tradingsymbol)

            coverage_percentage = ((expected_total - total_missing_candles) / expected_total * 100) if expected_total > 0 else 0

            result = {
                'date_range': {
                    'from_date': from_date.isoformat(),
                    'to_date': to_date.isoformat(),
                    'days': date_count
                },
                'total_stocks': total_stocks,
                'expected_total_candles': expected_total,
                'missing_candles': total_missing_candles,
                'coverage_percentage': round(coverage_percentage, 2),
                'stocks_with_complete_data': stocks_with_complete_data,
                'stocks_with_partial_data': stocks_with_partial_data,
                'stocks_with_no_data': stocks_with_no_data,
                'stocks_by_missing_count': stocks_by_missing_count
            }

            current_app.logger.info(
                f"Coverage analysis: {coverage_percentage:.2f}% "
                f"({expected_total - total_missing_candles}/{expected_total} candles)"
            )

            return result

        except Exception as e:
            current_app.logger.error(f"Error analyzing coverage: {str(e)}")
            return {
                'error': str(e),
                'date_range': {
                    'from_date': from_date.isoformat(),
                    'to_date': to_date.isoformat()
                }
            }

    @staticmethod
    def find_gap_ranges(
        tradingsymbol: str,
        from_date: date,
        to_date: date,
        interval: str = 'day'
    ) -> List[Tuple[date, date]]:
        """
        Find contiguous date ranges that are missing in historical data.

        Args:
            tradingsymbol: Trading symbol of the instrument
            from_date: Start date of the range to check
            to_date: End date of the range to check
            interval: Candle interval (default: 'day')

        Returns:
            List of tuples (gap_start_date, gap_end_date) representing contiguous gaps
        """
        try:
            missing_dates = GapDetectionService.find_missing_dates(
                tradingsymbol, from_date, to_date, interval
            )

            if not missing_dates:
                return []

            # Sort dates
            missing_dates.sort()

            # Group into contiguous ranges
            gap_ranges = []
            range_start = missing_dates[0]
            range_end = missing_dates[0]

            for i in range(1, len(missing_dates)):
                current_date = missing_dates[i]
                # Check if this date is consecutive to the previous one
                if (current_date - range_end).days == 1:
                    # Extend the current range
                    range_end = current_date
                else:
                    # Gap in the sequence, save current range and start a new one
                    gap_ranges.append((range_start, range_end))
                    range_start = current_date
                    range_end = current_date

            # Add the last range
            gap_ranges.append((range_start, range_end))

            current_app.logger.debug(
                f"Found {len(gap_ranges)} contiguous gap ranges for {tradingsymbol}"
            )
            return gap_ranges

        except Exception as e:
            current_app.logger.error(
                f"Error finding gap ranges for {tradingsymbol}: {str(e)}"
            )
            return []
