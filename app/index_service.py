"""
Sectorial Index Calculation Service

This service calculates market-cap-weighted indices for:
- Individual sectors (aggregate of all subsectors)
- Individual subsectors (aggregate of constituent stocks)
- Overall market (all NIFTY 500 stocks)

Uses free-float market cap weighting for realistic index calculation.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from flask import current_app
from sqlalchemy import and_, func
from app import db
from app.models import Instrument, StockInformation, Sector, SubSector


class IndexService:
    """
    Service for calculating market-cap-weighted indices
    """

    @staticmethod
    def calculate_sector_index(sector_id: int) -> Optional[Dict]:
        """
        Calculate index for a sector (aggregate of all stocks in all subsectors)

        Args:
            sector_id: ID of the sector

        Returns:
            Dictionary with index data or None if calculation fails
        """
        try:
            # Get all active subsectors for this sector
            subsectors = SubSector.query.filter_by(
                sector_id=sector_id,
                is_active=True
            ).all()

            if not subsectors:
                current_app.logger.warning(f"No active subsectors found for sector {sector_id}")
                return None

            subsector_ids = [ss.id for ss in subsectors]

            # Get all NIFTY 500 stocks in these subsectors with stock information
            stocks = db.session.query(
                Instrument,
                StockInformation
            ).join(
                StockInformation,
                Instrument.tradingsymbol == StockInformation.tradingsymbol
            ).filter(
                and_(
                    Instrument.sub_sector_id.in_(subsector_ids),
                    Instrument.exchange == 'NSE',
                    Instrument.instrument_type == 'EQ',
                    Instrument.is_nifty500 == True,
                    StockInformation.free_float_market_cap.isnot(None),
                    StockInformation.last_traded_price.isnot(None)
                )
            ).all()

            if not stocks:
                current_app.logger.warning(f"No stocks with market cap data found for sector {sector_id}")
                return None

            # Calculate total free-float market cap
            total_ff_market_cap = sum(stock_info.free_float_market_cap for _, stock_info in stocks)

            if total_ff_market_cap == 0:
                current_app.logger.warning(f"Total free-float market cap is zero for sector {sector_id}")
                return None

            # Calculate weighted index value
            index_value = 0
            total_market_cap = 0
            stock_count = len(stocks)

            for instrument, stock_info in stocks:
                weight = stock_info.free_float_market_cap / total_ff_market_cap
                contribution = stock_info.last_traded_price * weight
                index_value += contribution
                total_market_cap += stock_info.total_market_cap or 0

            # Normalize to base 100 (multiply by 100)
            normalized_index = index_value * 100

            current_app.logger.info(
                f"Calculated sector {sector_id} index: {normalized_index:.2f} "
                f"({stock_count} stocks, total MC: {total_market_cap:.2f} cr)"
            )

            return {
                'index_value': normalized_index,
                'total_market_cap': total_market_cap,
                'stock_count': stock_count,
                'calculated_at': datetime.utcnow()
            }

        except Exception as e:
            current_app.logger.error(f"Error calculating sector index for {sector_id}: {str(e)}")
            return None

    @staticmethod
    def calculate_subsector_index(subsector_id: int) -> Optional[Dict]:
        """
        Calculate index for a subsector (aggregate of constituent stocks)

        Args:
            subsector_id: ID of the subsector

        Returns:
            Dictionary with index data or None if calculation fails
        """
        try:
            # Get all NIFTY 500 stocks in this subsector with stock information
            stocks = db.session.query(
                Instrument,
                StockInformation
            ).join(
                StockInformation,
                Instrument.tradingsymbol == StockInformation.tradingsymbol
            ).filter(
                and_(
                    Instrument.sub_sector_id == subsector_id,
                    Instrument.exchange == 'NSE',
                    Instrument.instrument_type == 'EQ',
                    Instrument.is_nifty500 == True,
                    StockInformation.free_float_market_cap.isnot(None),
                    StockInformation.last_traded_price.isnot(None)
                )
            ).all()

            if not stocks:
                current_app.logger.warning(f"No stocks with market cap data found for subsector {subsector_id}")
                return None

            # Calculate total free-float market cap
            total_ff_market_cap = sum(stock_info.free_float_market_cap for _, stock_info in stocks)

            if total_ff_market_cap == 0:
                current_app.logger.warning(f"Total free-float market cap is zero for subsector {subsector_id}")
                return None

            # Calculate weighted index value
            index_value = 0
            total_market_cap = 0
            stock_count = len(stocks)

            for instrument, stock_info in stocks:
                weight = stock_info.free_float_market_cap / total_ff_market_cap
                contribution = stock_info.last_traded_price * weight
                index_value += contribution
                total_market_cap += stock_info.total_market_cap or 0

            # Normalize to base 100
            normalized_index = index_value * 100

            current_app.logger.info(
                f"Calculated subsector {subsector_id} index: {normalized_index:.2f} "
                f"({stock_count} stocks, total MC: {total_market_cap:.2f} cr)"
            )

            return {
                'index_value': normalized_index,
                'total_market_cap': total_market_cap,
                'stock_count': stock_count,
                'calculated_at': datetime.utcnow()
            }

        except Exception as e:
            current_app.logger.error(f"Error calculating subsector index for {subsector_id}: {str(e)}")
            return None

    @staticmethod
    def calculate_market_index() -> Optional[Dict]:
        """
        Calculate overall market index (all NIFTY 500 stocks)

        Returns:
            Dictionary with index data or None if calculation fails
        """
        try:
            # Get all NIFTY 500 stocks with stock information
            stocks = db.session.query(
                Instrument,
                StockInformation
            ).join(
                StockInformation,
                Instrument.tradingsymbol == StockInformation.tradingsymbol
            ).filter(
                and_(
                    Instrument.exchange == 'NSE',
                    Instrument.instrument_type == 'EQ',
                    Instrument.is_nifty500 == True,
                    StockInformation.free_float_market_cap.isnot(None),
                    StockInformation.last_traded_price.isnot(None)
                )
            ).all()

            if not stocks:
                current_app.logger.warning("No stocks with market cap data found for market index")
                return None

            # Calculate total free-float market cap
            total_ff_market_cap = sum(stock_info.free_float_market_cap for _, stock_info in stocks)

            if total_ff_market_cap == 0:
                current_app.logger.warning("Total free-float market cap is zero for market index")
                return None

            # Calculate weighted index value
            index_value = 0
            total_market_cap = 0
            stock_count = len(stocks)

            for instrument, stock_info in stocks:
                weight = stock_info.free_float_market_cap / total_ff_market_cap
                contribution = stock_info.last_traded_price * weight
                index_value += contribution
                total_market_cap += stock_info.total_market_cap or 0

            # Normalize to base 1000 for market index (to match NIFTY scale)
            normalized_index = index_value * 1000

            current_app.logger.info(
                f"Calculated market index: {normalized_index:.2f} "
                f"({stock_count} stocks, total MC: {total_market_cap:.2f} cr)"
            )

            return {
                'index_value': normalized_index,
                'total_market_cap': total_market_cap,
                'stock_count': stock_count,
                'calculated_at': datetime.utcnow()
            }

        except Exception as e:
            current_app.logger.error(f"Error calculating market index: {str(e)}")
            return None

    @staticmethod
    def get_subsector_stocks_contribution(subsector_id: int) -> List[Dict]:
        """
        Get detailed stock-level contributions to a subsector index

        Args:
            subsector_id: ID of the subsector

        Returns:
            List of dictionaries with stock contribution data
        """
        try:
            # Get all stocks in this subsector with stock information
            stocks = db.session.query(
                Instrument,
                StockInformation
            ).join(
                StockInformation,
                Instrument.tradingsymbol == StockInformation.tradingsymbol
            ).filter(
                and_(
                    Instrument.sub_sector_id == subsector_id,
                    Instrument.exchange == 'NSE',
                    Instrument.instrument_type == 'EQ',
                    Instrument.is_nifty500 == True,
                    StockInformation.free_float_market_cap.isnot(None),
                    StockInformation.last_traded_price.isnot(None)
                )
            ).all()

            if not stocks:
                return []

            # Calculate total free-float market cap
            total_ff_market_cap = sum(stock_info.free_float_market_cap for _, stock_info in stocks)

            if total_ff_market_cap == 0:
                return []

            # Build contribution list
            contributions = []
            for instrument, stock_info in stocks:
                weight = stock_info.free_float_market_cap / total_ff_market_cap
                weight_percent = weight * 100

                contributions.append({
                    'tradingsymbol': instrument.tradingsymbol,
                    'company_name': stock_info.company_name or instrument.name,
                    'last_traded_price': stock_info.last_traded_price,
                    'total_market_cap': stock_info.total_market_cap,
                    'free_float_market_cap': stock_info.free_float_market_cap,
                    'weight_percent': weight_percent,
                    'contribution': stock_info.last_traded_price * weight
                })

            # Sort by weight (highest contributors first)
            contributions.sort(key=lambda x: x['weight_percent'], reverse=True)

            return contributions

        except Exception as e:
            current_app.logger.error(f"Error getting stock contributions for subsector {subsector_id}: {str(e)}")
            return []
