"""
Stock Service - Handles individual stock CRUD operations
"""
from datetime import datetime
from flask import current_app
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Instrument, Nifty500List, SubSector
from app.kite_auth import get_kite_client
import requests


class StockService:
    """Service class for managing individual stock operations"""

    @staticmethod
    def fetch_sector_industry_from_nse(symbol):
        """
        Fetch sector and industry information from NSE API

        Args:
            symbol: Trading symbol (e.g., 'RELIANCE', 'INFY')

        Returns:
            dict: {'sector': 'sector_name', 'industry': 'industry_name'} or None
        """
        try:
            # NSE API endpoint for stock info
            url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.nseindia.com/'
            }

            # Create session to handle cookies
            session = requests.Session()
            session.get('https://www.nseindia.com/', headers=headers, timeout=10)

            # Fetch stock info
            response = session.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                info = data.get('info', {})

                sector = info.get('sector') or info.get('industry')
                industry = info.get('industryInfo') or info.get('basicIndustry')

                current_app.logger.info(f'Fetched sector/industry for {symbol}: sector={sector}, industry={industry}')

                return {
                    'sector': sector,
                    'industry': industry
                }
            else:
                current_app.logger.warning(f'NSE API returned status {response.status_code} for {symbol}')
                return None

        except Exception as e:
            current_app.logger.error(f'Error fetching sector/industry from NSE for {symbol}: {str(e)}')
            return None

    @staticmethod
    def fetch_stock_by_symbol(symbol, exchange='NSE'):
        """
        Fetch stock details from Kite API by trading symbol

        Handles stocks with suffixes like -BE, -BZ, etc. (T2T/Surveillance segments)

        Args:
            symbol: Trading symbol (e.g., 'RELIANCE', 'INFY', 'MAHSCOOTER')
            exchange: Exchange name (default: 'NSE')

        Returns:
            dict: Stock metadata from Kite API or None if not found
        """
        try:
            kite = get_kite_client()

            # Get all instruments for the exchange
            instruments = kite.instruments(exchange)

            symbol_upper = symbol.upper()

            # First try exact match
            for inst in instruments:
                if (inst.get('tradingsymbol') == symbol_upper and
                    inst.get('instrument_type') == 'EQ' and
                    inst.get('exchange') == exchange):

                    current_app.logger.info(f'Found stock {symbol} (exact match) in Kite API: {inst.get("name")}')
                    return inst

            # If no exact match, try matching with common NSE suffixes
            # -BE (Trade-to-Trade/BE Series), -BZ (Surveillance), -SM (Short delivery)
            common_suffixes = ['-BE', '-BZ', '-SM', '-GC', '-IL', '-BL']

            for suffix in common_suffixes:
                symbol_with_suffix = f"{symbol_upper}{suffix}"
                for inst in instruments:
                    if (inst.get('tradingsymbol') == symbol_with_suffix and
                        inst.get('instrument_type') == 'EQ' and
                        inst.get('exchange') == exchange):

                        current_app.logger.info(f'Found stock {symbol} with suffix {suffix} in Kite API: {inst.get("name")}')
                        return inst

            current_app.logger.warning(f'Stock {symbol} not found in Kite API for exchange {exchange}')
            return None

        except Exception as e:
            current_app.logger.error(f'Error fetching stock {symbol} from Kite API: {str(e)}')
            raise Exception(f'Failed to fetch stock data: {str(e)}')

    @staticmethod
    def add_stock(symbol, exchange='NSE'):
        """
        Add a new stock by fetching metadata from Kite API

        Args:
            symbol: Trading symbol
            exchange: Exchange name (default: 'NSE')

        Returns:
            tuple: (Instrument object, error_message)
        """
        try:
            symbol = symbol.upper().strip()

            # Fetch metadata from Kite API first
            stock_data = StockService.fetch_stock_by_symbol(symbol, exchange)

            if not stock_data:
                return None, f'Stock {symbol} not found in {exchange} exchange. Please verify the symbol.'

            # Check if stock already exists using the actual Kite trading symbol
            kite_tradingsymbol = stock_data.get('tradingsymbol')
            existing = Instrument.query.filter_by(
                tradingsymbol=kite_tradingsymbol,
                exchange=exchange
            ).first()

            if existing:
                return None, f'Stock {symbol} already exists in the database as {kite_tradingsymbol}'

            # Parse expiry date if exists
            expiry = None
            if stock_data.get('expiry'):
                from datetime import date
                if isinstance(stock_data.get('expiry'), date):
                    expiry = stock_data.get('expiry')
                elif isinstance(stock_data.get('expiry'), str):
                    try:
                        expiry = datetime.strptime(stock_data.get('expiry'), '%Y-%m-%d').date()
                    except:
                        pass

            # Extract base symbol (remove suffixes like -BE, -BZ, etc.)
            # This is needed to match against nifty500_list which stores base symbols
            base_symbol = symbol
            for suffix in ['-BE', '-BZ', '-SM', '-GC', '-IL', '-BL']:
                if kite_tradingsymbol.endswith(suffix):
                    base_symbol = kite_tradingsymbol.replace(suffix, '')
                    break

            # Check if it's a NIFTY 500 stock (using base symbol)
            is_nifty500 = Nifty500List.query.filter_by(
                symbol=base_symbol,
                is_active=True
            ).first() is not None

            # Fetch sector and industry from NSE API (for NSE stocks only)
            # Use base symbol for NSE API (without suffixes)
            sector = None
            sub_sector = None
            if exchange == 'NSE':
                try:
                    sector_info = StockService.fetch_sector_industry_from_nse(base_symbol)
                    if sector_info:
                        sector = sector_info.get('sector')
                        sub_sector = sector_info.get('industry')
                        current_app.logger.info(f'NSE data for {base_symbol}: sector={sector}, industry={sub_sector}')
                except Exception as e:
                    current_app.logger.warning(f'Could not fetch NSE sector/industry for {base_symbol}: {str(e)}')

            # Create new instrument
            instrument = Instrument(
                instrument_token=stock_data.get('instrument_token'),
                exchange_token=stock_data.get('exchange_token'),
                tradingsymbol=kite_tradingsymbol,  # Use Kite's actual trading symbol
                name=stock_data.get('name'),
                expiry=expiry,
                strike=stock_data.get('strike', 0.0),
                tick_size=stock_data.get('tick_size', 0.05),
                lot_size=stock_data.get('lot_size', 1),
                instrument_type=stock_data.get('instrument_type', 'EQ'),
                segment=stock_data.get('segment', exchange),
                exchange=exchange,
                sector=sector,
                sub_sector=sub_sector,
                is_nifty500=is_nifty500,
                last_price=0.0
            )

            db.session.add(instrument)
            db.session.commit()

            current_app.logger.info(f'Successfully added stock {symbol} (ID: {instrument.id})')
            return instrument, None

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f'Integrity error adding stock {symbol}: {str(e)}')
            return None, f'Stock {symbol} already exists or database constraint violated'

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error adding stock {symbol}: {str(e)}')
            return None, f'Failed to add stock: {str(e)}'

    @staticmethod
    def update_stock(stock_id, name=None, sub_sector_id=None):
        """
        Update stock information

        Args:
            stock_id: Stock database ID
            name: Updated name (optional)
            sub_sector_id: Updated sub-sector ID (optional)

        Returns:
            tuple: (Instrument object, error_message)
        """
        try:
            instrument = Instrument.query.get(stock_id)

            if not instrument:
                return None, 'Stock not found'

            # Update fields if provided
            if name is not None:
                instrument.name = name

            if sub_sector_id is not None:
                # Validate sub_sector exists
                if sub_sector_id:
                    sub_sector = SubSector.query.get(sub_sector_id)
                    if not sub_sector:
                        return None, 'Invalid sub-sector selected'
                instrument.sub_sector_id = sub_sector_id if sub_sector_id else None

            instrument.last_updated = datetime.utcnow()
            db.session.commit()

            current_app.logger.info(f'Successfully updated stock {instrument.tradingsymbol} (ID: {stock_id})')
            return instrument, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error updating stock {stock_id}: {str(e)}')
            return None, f'Failed to update stock: {str(e)}'

    @staticmethod
    def delete_stock(stock_id):
        """
        Delete a stock from the database

        Args:
            stock_id: Stock database ID

        Returns:
            tuple: (success_boolean, error_message)
        """
        try:
            instrument = Instrument.query.get(stock_id)

            if not instrument:
                return False, 'Stock not found'

            symbol = instrument.tradingsymbol

            # Check if stock is used in watchlists
            watchlist_count = len(instrument.watchlist_items)
            if watchlist_count > 0:
                return False, f'Cannot delete {symbol}. It is being used in {watchlist_count} watchlist(s).'

            # Check if stock has orders
            orders_count = len(instrument.orders)
            if orders_count > 0:
                return False, f'Cannot delete {symbol}. It has {orders_count} associated order(s).'

            # Check if stock has positions
            positions_count = len(instrument.positions)
            if positions_count > 0:
                return False, f'Cannot delete {symbol}. It has {positions_count} associated position(s).'

            db.session.delete(instrument)
            db.session.commit()

            current_app.logger.info(f'Successfully deleted stock {symbol} (ID: {stock_id})')
            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error deleting stock {stock_id}: {str(e)}')
            return False, f'Failed to delete stock: {str(e)}'

    @staticmethod
    def get_stock(stock_id):
        """
        Get stock by ID

        Args:
            stock_id: Stock database ID

        Returns:
            Instrument object or None
        """
        return Instrument.query.get(stock_id)

    @staticmethod
    def search_stocks(query, exchange=None, limit=50):
        """
        Search stocks by symbol or name

        Args:
            query: Search query
            exchange: Optional exchange filter
            limit: Maximum results

        Returns:
            list: List of Instrument objects
        """
        search_filter = (
            Instrument.tradingsymbol.ilike(f'%{query}%') |
            Instrument.name.ilike(f'%{query}%')
        )

        if exchange:
            search_filter = search_filter & (Instrument.exchange == exchange)

        return Instrument.query.filter(search_filter).limit(limit).all()

    @staticmethod
    def get_all_stocks(page=1, per_page=50, exchange='NSE', instrument_type='EQ', nifty500_only=False):
        """
        Get paginated list of stocks

        Args:
            page: Page number
            per_page: Items per page
            exchange: Exchange filter
            instrument_type: Instrument type filter
            nifty500_only: Filter only NIFTY 500 stocks

        Returns:
            Pagination object
        """
        query = Instrument.query.filter_by(
            exchange=exchange,
            instrument_type=instrument_type
        )

        if nifty500_only:
            query = query.filter_by(is_nifty500=True)

        query = query.order_by(Instrument.tradingsymbol)

        return query.paginate(page=page, per_page=per_page, error_out=False)
