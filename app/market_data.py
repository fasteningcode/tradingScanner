import json
import logging
from datetime import datetime, timedelta
from threading import Thread
from kiteconnect import KiteTicker
from flask import current_app
from app import db
from app.models import MarketQuote, Instrument
from app.kite_auth import get_kite_client


class MarketDataService:
    """
    Service for managing real-time market data via KiteTicker WebSocket
    Handles live quote streaming and quote caching
    """

    def __init__(self, api_key, access_token):
        """
        Initialize MarketDataService

        Args:
            api_key: Kite Connect API key
            access_token: User's Kite access token
        """
        self.api_key = api_key
        self.access_token = access_token
        self.ticker = None
        self.subscribed_tokens = set()
        self.quote_callbacks = []
        self.logger = logging.getLogger(__name__)

    def initialize_ticker(self):
        """Initialize KiteTicker instance with callbacks"""
        if self.ticker:
            return

        self.ticker = KiteTicker(self.api_key, self.access_token)

        # Set up callbacks
        self.ticker.on_ticks = self.on_ticks
        self.ticker.on_connect = self.on_connect
        self.ticker.on_close = self.on_close
        self.ticker.on_error = self.on_error
        self.ticker.on_reconnect = self.on_reconnect
        self.ticker.on_noreconnect = self.on_noreconnect

        self.logger.info('KiteTicker initialized')

    def on_ticks(self, ws, ticks):
        """
        Callback when ticks are received

        Args:
            ws: WebSocket instance
            ticks: List of tick data
        """
        try:
            for tick in ticks:
                # Store tick in database
                self.store_quote(tick)

                # Call registered callbacks
                for callback in self.quote_callbacks:
                    try:
                        callback(tick)
                    except Exception as e:
                        self.logger.error(f'Error in quote callback: {str(e)}')

        except Exception as e:
            self.logger.error(f'Error processing ticks: {str(e)}')

    def on_connect(self, ws, response):
        """Callback on successful connection"""
        self.logger.info(f'WebSocket connected: {response}')

        # Subscribe to tokens if any were added before connection
        if self.subscribed_tokens:
            ws.subscribe(list(self.subscribed_tokens))
            ws.set_mode(ws.MODE_FULL, list(self.subscribed_tokens))

    def on_close(self, ws, code, reason):
        """Callback when connection is closed"""
        self.logger.warning(f'WebSocket closed: {code} - {reason}')

    def on_error(self, ws, code, reason):
        """Callback when error occurs"""
        self.logger.error(f'WebSocket error: {code} - {reason}')

    def on_reconnect(self, ws, attempts_count):
        """Callback when reconnecting"""
        self.logger.info(f'WebSocket reconnecting (attempt {attempts_count})')

    def on_noreconnect(self, ws):
        """Callback when reconnection fails"""
        self.logger.error('WebSocket reconnection failed')

    def connect(self):
        """Start WebSocket connection in a separate thread"""
        if not self.ticker:
            self.initialize_ticker()

        # Start ticker in a separate thread
        ticker_thread = Thread(target=self.ticker.connect, daemon=True)
        ticker_thread.start()
        self.logger.info('WebSocket connection started')

    def disconnect(self):
        """Close WebSocket connection"""
        if self.ticker:
            self.ticker.close()
            self.logger.info('WebSocket connection closed')

    def subscribe(self, instrument_tokens, mode='full'):
        """
        Subscribe to instrument tokens

        Args:
            instrument_tokens: List of instrument tokens or single token
            mode: Subscription mode ('ltp', 'quote', 'full')
        """
        if isinstance(instrument_tokens, int):
            instrument_tokens = [instrument_tokens]

        self.subscribed_tokens.update(instrument_tokens)

        if self.ticker and self.ticker.is_connected():
            self.ticker.subscribe(instrument_tokens)

            # Set mode
            if mode == 'ltp':
                self.ticker.set_mode(self.ticker.MODE_LTP, instrument_tokens)
            elif mode == 'quote':
                self.ticker.set_mode(self.ticker.MODE_QUOTE, instrument_tokens)
            else:  # full
                self.ticker.set_mode(self.ticker.MODE_FULL, instrument_tokens)

            self.logger.info(f'Subscribed to {len(instrument_tokens)} instruments in {mode} mode')

    def unsubscribe(self, instrument_tokens):
        """
        Unsubscribe from instrument tokens

        Args:
            instrument_tokens: List of instrument tokens or single token
        """
        if isinstance(instrument_tokens, int):
            instrument_tokens = [instrument_tokens]

        self.subscribed_tokens.difference_update(instrument_tokens)

        if self.ticker and self.ticker.is_connected():
            self.ticker.unsubscribe(instrument_tokens)
            self.logger.info(f'Unsubscribed from {len(instrument_tokens)} instruments')

    def register_callback(self, callback):
        """
        Register a callback function to be called on each tick

        Args:
            callback: Function that takes tick data as parameter
        """
        self.quote_callbacks.append(callback)

    def store_quote(self, tick):
        """
        Store quote data in database

        Args:
            tick: Tick data dictionary from KiteTicker
        """
        try:
            instrument_token = tick.get('instrument_token')
            if not instrument_token:
                return

            # Find instrument in database
            instrument = Instrument.query.filter_by(instrument_token=instrument_token).first()
            if not instrument:
                return

            # Update instrument last price
            instrument.last_price = tick.get('last_price', 0.0)

            # Create or update market quote
            quote = MarketQuote(
                instrument_id=instrument.id,
                last_price=tick.get('last_price', 0.0),
                last_quantity=tick.get('last_quantity', 0),
                average_price=tick.get('average_price', 0.0),
                volume=tick.get('volume', 0),
                buy_quantity=tick.get('buy_quantity', 0),
                sell_quantity=tick.get('sell_quantity', 0),
                open_price=tick.get('ohlc', {}).get('open', 0.0),
                high_price=tick.get('ohlc', {}).get('high', 0.0),
                low_price=tick.get('ohlc', {}).get('low', 0.0),
                close_price=tick.get('ohlc', {}).get('close', 0.0),
                change=tick.get('change', 0.0),
                change_percent=tick.get('change_percent', 0.0) if 'change_percent' in tick else 0.0,
                timestamp=datetime.fromtimestamp(tick.get('timestamp').timestamp()) if tick.get('timestamp') else datetime.utcnow(),
                last_trade_time=datetime.fromtimestamp(tick.get('last_trade_time').timestamp()) if tick.get('last_trade_time') else None
            )

            db.session.add(quote)
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            self.logger.error(f'Error storing quote: {str(e)}')

    @staticmethod
    def get_quotes(instrument_tokens):
        """
        Get current quotes for instruments using REST API

        Args:
            instrument_tokens: List of instrument tokens or single token

        Returns:
            dict: Quote data
        """
        try:
            kite = get_kite_client()

            if isinstance(instrument_tokens, int):
                instrument_tokens = [instrument_tokens]

            # Format tokens with exchange prefix
            formatted_tokens = []
            for token in instrument_tokens:
                instrument = Instrument.query.filter_by(instrument_token=token).first()
                if instrument:
                    formatted_tokens.append(f'{instrument.exchange}:{token}')

            quotes = kite.quote(formatted_tokens)
            return quotes

        except Exception as e:
            current_app.logger.error(f'Error fetching quotes: {str(e)}')
            raise

    @staticmethod
    def get_ohlc(instrument_tokens):
        """
        Get OHLC data for instruments

        Args:
            instrument_tokens: List of instrument tokens or single token

        Returns:
            dict: OHLC data
        """
        try:
            kite = get_kite_client()

            if isinstance(instrument_tokens, int):
                instrument_tokens = [instrument_tokens]

            # Format tokens with exchange prefix
            formatted_tokens = []
            for token in instrument_tokens:
                instrument = Instrument.query.filter_by(instrument_token=token).first()
                if instrument:
                    formatted_tokens.append(f'{instrument.exchange}:{token}')

            ohlc = kite.ohlc(formatted_tokens)
            return ohlc

        except Exception as e:
            current_app.logger.error(f'Error fetching OHLC: {str(e)}')
            raise

    @staticmethod
    def get_ltp(instrument_tokens):
        """
        Get Last Traded Price for instruments

        Args:
            instrument_tokens: List of instrument tokens or single token

        Returns:
            dict: LTP data
        """
        try:
            kite = get_kite_client()

            if isinstance(instrument_tokens, int):
                instrument_tokens = [instrument_tokens]

            # Format tokens with exchange prefix
            formatted_tokens = []
            for token in instrument_tokens:
                instrument = Instrument.query.filter_by(instrument_token=token).first()
                if instrument:
                    formatted_tokens.append(f'{instrument.exchange}:{token}')

            ltp = kite.ltp(formatted_tokens)
            return ltp

        except Exception as e:
            current_app.logger.error(f'Error fetching LTP: {str(e)}')
            raise

    @staticmethod
    def get_historical_data(instrument_token, from_date, to_date, interval='day'):
        """
        Get historical candle data

        Args:
            instrument_token: Instrument token
            from_date: Start date (datetime object or string 'YYYY-MM-DD')
            to_date: End date (datetime object or string 'YYYY-MM-DD')
            interval: Candle interval (minute, day, 3minute, 5minute, 10minute, 15minute,
                     30minute, 60minute, day)

        Returns:
            list: List of historical candles
        """
        try:
            kite = get_kite_client()
            historical_data = kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            return historical_data

        except Exception as e:
            current_app.logger.error(f'Error fetching historical data: {str(e)}')
            raise

    @staticmethod
    def get_cached_quote(instrument_id, minutes=5):
        """
        Get cached quote from database

        Args:
            instrument_id: Instrument database ID
            minutes: How old the quote can be (in minutes)

        Returns:
            MarketQuote: Cached quote or None
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        quote = MarketQuote.query.filter(
            MarketQuote.instrument_id == instrument_id,
            MarketQuote.timestamp >= cutoff_time
        ).order_by(MarketQuote.timestamp.desc()).first()

        return quote


# Global market data service instance (to be initialized per user)
_market_data_services = {}


def get_market_data_service(user_id, api_key, access_token):
    """
    Get or create MarketDataService instance for a user

    Args:
        user_id: User ID
        api_key: Kite API key
        access_token: User's Kite access token

    Returns:
        MarketDataService: Market data service instance
    """
    if user_id not in _market_data_services:
        _market_data_services[user_id] = MarketDataService(api_key, access_token)

    return _market_data_services[user_id]


def cleanup_market_data_service(user_id):
    """
    Cleanup and remove market data service for a user

    Args:
        user_id: User ID
    """
    if user_id in _market_data_services:
        service = _market_data_services[user_id]
        service.disconnect()
        del _market_data_services[user_id]
