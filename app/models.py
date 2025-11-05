from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


class User(UserMixin, db.Model):
    """User model for authentication and profile management"""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Kite Connect credentials
    kite_access_token = db.Column(db.String(255), nullable=True)
    kite_access_token_expires = db.Column(db.DateTime, nullable=True)
    kite_user_id = db.Column(db.String(100), nullable=True)
    kite_public_token = db.Column(db.String(255), nullable=True)
    kite_refresh_token = db.Column(db.String(255), nullable=True)
    kite_connected = db.Column(db.Boolean, default=False)
    kite_last_connected = db.Column(db.DateTime, nullable=True)

    # Relationships
    watchlists = db.relationship('Watchlist', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    orders = db.relationship('Order', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    positions = db.relationship('Position', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    scan_results = db.relationship('ScanResult', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    backtest_strategies = db.relationship('BacktestStrategy', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    backtest_results = db.relationship('BacktestResult', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        """Hash and set the user's password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify the user's password"""
        return check_password_hash(self.password_hash, password)

    def update_last_login(self):
        """Update the last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()

    def update_kite_credentials(self, access_token, user_id, public_token=None, refresh_token=None, expires_at=None):
        """Update Kite Connect credentials"""
        self.kite_access_token = access_token
        self.kite_user_id = user_id
        self.kite_public_token = public_token
        self.kite_refresh_token = refresh_token
        self.kite_access_token_expires = expires_at
        self.kite_connected = True
        self.kite_last_connected = datetime.utcnow()
        db.session.commit()

    def is_kite_token_valid(self):
        """Check if Kite access token is still valid"""
        if not self.kite_access_token or not self.kite_access_token_expires:
            return False
        return datetime.utcnow() < self.kite_access_token_expires


class Sector(db.Model):
    """Model for sector/industry classification"""

    __tablename__ = 'sectors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(50), nullable=True)  # Bootstrap icon class
    color = db.Column(db.String(20), nullable=True)  # Color for visualization
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sub_sectors = db.relationship('SubSector', back_populates='sector', lazy='dynamic',
                                  cascade='all, delete-orphan', order_by='SubSector.display_order')

    def __repr__(self):
        return f'<Sector {self.name}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'color': self.color,
            'is_active': self.is_active,
            'display_order': self.display_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'sub_sectors_count': self.sub_sectors.count()
        }


class SubSector(db.Model):
    """Model for sub-sector classification within sectors"""

    __tablename__ = 'sub_sectors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    sector_id = db.Column(db.Integer, db.ForeignKey('sectors.id'), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sector = db.relationship('Sector', back_populates='sub_sectors')
    instruments = db.relationship('Instrument', back_populates='sub_sector_obj', lazy='dynamic')

    # Unique constraint: sub-sector name must be unique within a sector
    __table_args__ = (
        db.UniqueConstraint('sector_id', 'name', name='uq_sector_subsector'),
    )

    def __repr__(self):
        return f'<SubSector {self.name} in {self.sector.name if self.sector else "N/A"}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'sector_id': self.sector_id,
            'sector_name': self.sector.name if self.sector else None,
            'description': self.description,
            'is_active': self.is_active,
            'display_order': self.display_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'instruments_count': self.instruments.filter_by(is_nifty500=True).count()
        }


class Nifty500List(db.Model):
    """Model for storing NIFTY 500 stock symbols"""

    __tablename__ = 'nifty500_list'

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(50), unique=True, nullable=False, index=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Nifty500 {self.symbol}>'


class Instrument(db.Model):
    """Model for storing instrument/stock data with custom sector mapping"""

    __tablename__ = 'instruments'

    id = db.Column(db.Integer, primary_key=True)
    instrument_token = db.Column(db.Integer, unique=True, nullable=False, index=True)
    exchange_token = db.Column(db.Integer, nullable=True)
    tradingsymbol = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=True)
    last_price = db.Column(db.Float, default=0.0)
    expiry = db.Column(db.Date, nullable=True)
    strike = db.Column(db.Float, nullable=True)
    tick_size = db.Column(db.Float, default=0.05)
    lot_size = db.Column(db.Integer, default=1)
    instrument_type = db.Column(db.String(10), nullable=False)  # EQ, FUT, CE, PE, etc.
    segment = db.Column(db.String(10), nullable=False)  # NSE, BSE, NFO, etc.
    exchange = db.Column(db.String(10), nullable=False)

    # Custom sector/industry classification
    # DEPRECATED: These fields are kept for backward compatibility during migration
    sector = db.Column(db.String(100), nullable=True, index=True)  # DEPRECATED - use sub_sector_obj.sector
    sub_sector = db.Column(db.String(100), nullable=True, index=True)  # DEPRECATED - use sub_sector_obj
    custom_tags = db.Column(db.Text, nullable=True)  # JSON string for custom tags

    # New relational sub-sector reference
    sub_sector_id = db.Column(db.Integer, db.ForeignKey('sub_sectors.id'), nullable=True, index=True)

    # NIFTY 500 flag
    is_nifty500 = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # Timestamps
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    sub_sector_obj = db.relationship('SubSector', back_populates='instruments')
    watchlist_items = db.relationship('WatchlistItem', back_populates='instrument', cascade='all, delete-orphan')
    orders = db.relationship('Order', back_populates='instrument')
    positions = db.relationship('Position', back_populates='instrument')
    market_quotes = db.relationship('MarketQuote', back_populates='instrument', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Instrument {self.tradingsymbol} ({self.exchange})>'


class Watchlist(db.Model):
    """User watchlists"""

    __tablename__ = 'watchlists'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', back_populates='watchlists')
    items = db.relationship('WatchlistItem', back_populates='watchlist', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Watchlist {self.name}>'


class WatchlistItem(db.Model):
    """Items in watchlists"""

    __tablename__ = 'watchlist_items'

    id = db.Column(db.Integer, primary_key=True)
    watchlist_id = db.Column(db.Integer, db.ForeignKey('watchlists.id'), nullable=False)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    watchlist = db.relationship('Watchlist', back_populates='items')
    instrument = db.relationship('Instrument', back_populates='watchlist_items')

    def __repr__(self):
        return f'<WatchlistItem {self.watchlist_id}:{self.instrument_id}>'


class Order(db.Model):
    """Trading orders"""

    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=False)

    # Kite order details
    order_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    exchange_order_id = db.Column(db.String(50), nullable=True)
    parent_order_id = db.Column(db.String(50), nullable=True)

    # Order parameters
    transaction_type = db.Column(db.String(10), nullable=False)  # BUY, SELL
    order_type = db.Column(db.String(20), nullable=False)  # MARKET, LIMIT, SL, SL-M
    product = db.Column(db.String(10), nullable=False)  # CNC, MIS, NRML
    variety = db.Column(db.String(20), nullable=False)  # regular, amo, co, iceberg
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, default=0.0)
    trigger_price = db.Column(db.Float, default=0.0)
    disclosed_quantity = db.Column(db.Integer, default=0)

    # Order status
    status = db.Column(db.String(20), nullable=False, index=True)  # OPEN, COMPLETE, CANCELLED, REJECTED
    status_message = db.Column(db.Text, nullable=True)
    filled_quantity = db.Column(db.Integer, default=0)
    pending_quantity = db.Column(db.Integer, default=0)
    average_price = db.Column(db.Float, default=0.0)

    # Timestamps
    order_timestamp = db.Column(db.DateTime, nullable=False)
    exchange_timestamp = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', back_populates='orders')
    instrument = db.relationship('Instrument', back_populates='orders')

    def __repr__(self):
        return f'<Order {self.order_id} {self.transaction_type} {self.quantity}>'


class Position(db.Model):
    """Trading positions"""

    __tablename__ = 'positions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=False)

    # Position details
    product = db.Column(db.String(10), nullable=False)  # CNC, MIS, NRML
    quantity = db.Column(db.Integer, nullable=False)
    overnight_quantity = db.Column(db.Integer, default=0)
    multiplier = db.Column(db.Float, default=1.0)

    # Price and P&L
    average_price = db.Column(db.Float, nullable=False)
    buy_price = db.Column(db.Float, default=0.0)
    sell_price = db.Column(db.Float, default=0.0)
    buy_quantity = db.Column(db.Integer, default=0)
    sell_quantity = db.Column(db.Integer, default=0)
    buy_value = db.Column(db.Float, default=0.0)
    sell_value = db.Column(db.Float, default=0.0)
    pnl = db.Column(db.Float, default=0.0)
    realised = db.Column(db.Float, default=0.0)
    unrealised = db.Column(db.Float, default=0.0)

    # Timestamps
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', back_populates='positions')
    instrument = db.relationship('Instrument', back_populates='positions')

    def __repr__(self):
        return f'<Position {self.product} {self.quantity}>'


class ScannerStrategy(db.Model):
    """Scanner strategies configuration"""

    __tablename__ = 'scanner_strategies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    strategy_type = db.Column(db.String(50), nullable=False)  # volume_breakout, price_breakout, rsi, custom
    parameters = db.Column(db.Text, nullable=True)  # JSON string for strategy parameters
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    scan_results = db.relationship('ScanResult', back_populates='strategy', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ScannerStrategy {self.name}>'


class ScanResult(db.Model):
    """Results from scanner runs"""

    __tablename__ = 'scan_results'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    strategy_id = db.Column(db.Integer, db.ForeignKey('scanner_strategies.id'), nullable=False)
    instrument_token = db.Column(db.Integer, nullable=False, index=True)
    tradingsymbol = db.Column(db.String(50), nullable=False)

    # Scan result data
    scan_data = db.Column(db.Text, nullable=True)  # JSON string with scan metrics
    signal_strength = db.Column(db.Float, default=0.0)
    scan_timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = db.relationship('User', back_populates='scan_results')
    strategy = db.relationship('ScannerStrategy', back_populates='scan_results')

    def __repr__(self):
        return f'<ScanResult {self.tradingsymbol} at {self.scan_timestamp}>'


class MarketQuote(db.Model):
    """Real-time and historical market quotes cache"""

    __tablename__ = 'market_quotes'

    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=False)

    # Quote data
    last_price = db.Column(db.Float, nullable=False)
    last_quantity = db.Column(db.Integer, default=0)
    average_price = db.Column(db.Float, default=0.0)
    volume = db.Column(db.Integer, default=0)
    buy_quantity = db.Column(db.Integer, default=0)
    sell_quantity = db.Column(db.Integer, default=0)

    # OHLC
    open_price = db.Column(db.Float, default=0.0)
    high_price = db.Column(db.Float, default=0.0)
    low_price = db.Column(db.Float, default=0.0)
    close_price = db.Column(db.Float, default=0.0)

    # Change
    change = db.Column(db.Float, default=0.0)
    change_percent = db.Column(db.Float, default=0.0)

    # Timestamps
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    last_trade_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    instrument = db.relationship('Instrument', back_populates='market_quotes')

    def __repr__(self):
        return f'<MarketQuote {self.instrument_id} @ {self.last_price}>'


class BacktestStrategy(db.Model):
    """Backtest strategies configuration"""

    __tablename__ = 'backtest_strategies'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    strategy_code = db.Column(db.Text, nullable=True)  # Python code or JSON config
    parameters = db.Column(db.Text, nullable=True)  # JSON string for parameters
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', back_populates='backtest_strategies')
    results = db.relationship('BacktestResult', back_populates='strategy', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<BacktestStrategy {self.name}>'


class BacktestResult(db.Model):
    """Results from backtest runs"""

    __tablename__ = 'backtest_results'

    id = db.Column(db.Integer, primary_key=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey('backtest_strategies.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    instrument_token = db.Column(db.Integer, nullable=False)
    tradingsymbol = db.Column(db.String(50), nullable=False)

    # Backtest parameters
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    initial_capital = db.Column(db.Float, nullable=False)
    commission = db.Column(db.Float, default=0.0)

    # Results
    final_capital = db.Column(db.Float, nullable=False)
    total_return = db.Column(db.Float, nullable=False)  # Percentage
    total_trades = db.Column(db.Integer, default=0)
    winning_trades = db.Column(db.Integer, default=0)
    losing_trades = db.Column(db.Integer, default=0)
    win_rate = db.Column(db.Float, default=0.0)  # Percentage
    max_drawdown = db.Column(db.Float, default=0.0)  # Percentage
    sharpe_ratio = db.Column(db.Float, default=0.0)

    # Detailed results
    results_data = db.Column(db.Text, nullable=True)  # JSON string with trade log and equity curve

    # Timestamps
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', back_populates='backtest_results')
    strategy = db.relationship('BacktestStrategy', back_populates='results')

    def __repr__(self):
        return f'<BacktestResult {self.tradingsymbol} Return: {self.total_return}%>'


class HistoricalDataSettings(db.Model):
    """Model for storing user's historical data download preferences"""

    __tablename__ = 'historical_data_settings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)

    # Rate limiting
    requests_per_second = db.Column(db.Integer, default=1, nullable=False)  # 1-3 requests per second

    # Date range settings
    date_preset = db.Column(db.String(20), default='1month')  # '1day', '1week', '1month', '3months', '6months', '1year', '5years', '10years', 'custom'
    from_date = db.Column(db.Date, nullable=True)  # Used when date_preset is 'custom'
    to_date = db.Column(db.Date, nullable=True)  # Used when date_preset is 'custom'

    # Candle interval
    candle_interval = db.Column(db.String(20), default='day')  # 'minute', '3minute', '5minute', '10minute', '15minute', '30minute', '60minute', 'day'

    # Download behavior
    continuous_download = db.Column(db.Boolean, default=False)  # Enable continuous background downloads
    auto_download_new_stocks = db.Column(db.Boolean, default=False)  # Auto-download when new stocks are added

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('historical_data_settings', uselist=False))

    def __repr__(self):
        return f'<HistoricalDataSettings User:{self.user_id} Interval:{self.candle_interval}>'


class HistoricalData(db.Model):
    """Model for storing historical candlestick data in JSON format (one row per stock per interval)"""

    __tablename__ = 'historical_data'

    id = db.Column(db.Integer, primary_key=True)
    tradingsymbol = db.Column(db.String(50), nullable=False, index=True)
    last_downloaded = db.Column(db.DateTime, nullable=True)  # When data was last fetched
    interval = db.Column(db.String(20), nullable=False, index=True)  # 'minute', '3minute', '5minute', '10minute', '15minute', '30minute', '60minute', 'day'

    # Candlestick data stored as JSON array
    # Format: [{"date": "2024-01-01", "open": 100.0, "high": 105.0, "low": 99.0, "close": 103.0, "volume": 1000, "oi": 0}, ...]
    candlestick_data = db.Column(db.Text, nullable=False)  # Stored as JSON text

    # Metadata
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    updated_on = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint: One row per stock per interval
    __table_args__ = (
        db.UniqueConstraint('tradingsymbol', 'interval', name='uq_tradingsymbol_interval'),
        db.Index('ix_historical_data_lookup', 'tradingsymbol', 'interval'),
    )

    def __repr__(self):
        return f'<HistoricalData {self.tradingsymbol} [{self.interval}]>'

    def get_candles(self):
        """Parse and return candlestick data as Python list"""
        import json
        try:
            return json.loads(self.candlestick_data) if self.candlestick_data else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_candles(self, candles_list):
        """Set candlestick data from Python list (converts to JSON)"""
        import json
        self.candlestick_data = json.dumps(candles_list)
        self.updated_on = datetime.utcnow()

    def get_date_range(self):
        """Get earliest and latest dates from candlestick data"""
        candles = self.get_candles()
        if not candles:
            return None, None

        dates = [c.get('date') for c in candles if c.get('date')]
        if not dates:
            return None, None

        return min(dates), max(dates)

    def get_candle_count(self):
        """Get total number of candles"""
        return len(self.get_candles())

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        earliest, latest = self.get_date_range()
        return {
            'id': self.id,
            'tradingsymbol': self.tradingsymbol,
            'interval': self.interval,
            'last_downloaded': self.last_downloaded.isoformat() if self.last_downloaded else None,
            'candle_count': self.get_candle_count(),
            'earliest_date': earliest,
            'latest_date': latest,
            'created_on': self.created_on.isoformat() if self.created_on else None,
            'updated_on': self.updated_on.isoformat() if self.updated_on else None
        }


class DownloadTask(db.Model):
    """Model for tracking historical data download tasks"""

    __tablename__ = 'download_tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Task configuration
    interval = db.Column(db.String(20), nullable=False)  # Candle interval being downloaded
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    requests_per_second = db.Column(db.Integer, default=1)

    # Progress tracking
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # 'pending', 'running', 'paused', 'completed', 'failed', 'cancelled'
    progress_percentage = db.Column(db.Float, default=0.0)
    total_stocks = db.Column(db.Integer, default=0)
    completed_stocks = db.Column(db.Integer, default=0)
    failed_stocks = db.Column(db.Integer, default=0)
    skipped_stocks = db.Column(db.Integer, default=0)  # Already had data
    current_stock_symbol = db.Column(db.String(50), nullable=True)
    current_stock_id = db.Column(db.Integer, nullable=True)  # Last processed instrument_id for resume

    # Statistics
    total_records_downloaded = db.Column(db.Integer, default=0)
    total_api_calls = db.Column(db.Integer, default=0)

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    paused_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Error handling
    error_message = db.Column(db.Text, nullable=True)
    error_count = db.Column(db.Integer, default=0)

    # Relationships
    user = db.relationship('User', backref=db.backref('download_tasks', lazy='dynamic', cascade='all, delete-orphan'))
    logs = db.relationship('DownloadLog', back_populates='task', lazy='dynamic', cascade='all, delete-orphan', order_by='DownloadLog.created_at.desc()')

    def __repr__(self):
        return f'<DownloadTask {self.id} User:{self.user_id} Status:{self.status} Progress:{self.progress_percentage}%>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'status': self.status,
            'progress_percentage': round(self.progress_percentage, 2),
            'total_stocks': self.total_stocks,
            'completed_stocks': self.completed_stocks,
            'failed_stocks': self.failed_stocks,
            'skipped_stocks': self.skipped_stocks,
            'current_stock_symbol': self.current_stock_symbol,
            'total_records_downloaded': self.total_records_downloaded,
            'total_api_calls': self.total_api_calls,
            'interval': self.interval,
            'from_date': self.from_date.isoformat() if self.from_date else None,
            'to_date': self.to_date.isoformat() if self.to_date else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'error_count': self.error_count
        }

    def calculate_eta(self):
        """Calculate estimated time to completion in seconds"""
        if self.status != 'running' or not self.started_at or self.completed_stocks == 0:
            return None

        elapsed = (datetime.utcnow() - self.started_at).total_seconds()
        avg_time_per_stock = elapsed / self.completed_stocks
        remaining_stocks = self.total_stocks - self.completed_stocks
        return remaining_stocks * avg_time_per_stock


class DownloadLog(db.Model):
    """Model for logging individual stock download results"""

    __tablename__ = 'download_logs'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('download_tasks.id'), nullable=False, index=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=False, index=True)

    # Download details
    symbol = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'success', 'failed', 'skipped'
    records_downloaded = db.Column(db.Integer, default=0)
    api_calls_made = db.Column(db.Integer, default=0)

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Error handling
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0)

    # Relationships
    task = db.relationship('DownloadTask', back_populates='logs')
    instrument = db.relationship('Instrument', backref=db.backref('download_logs', lazy='dynamic'))

    def __repr__(self):
        return f'<DownloadLog Task:{self.task_id} {self.symbol} Status:{self.status}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'status': self.status,
            'records_downloaded': self.records_downloaded,
            'api_calls_made': self.api_calls_made,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'retry_count': self.retry_count
        }


class StockInformation(db.Model):
    """Model for storing stock fundamental information from NSE"""

    __tablename__ = 'stock_information'

    id = db.Column(db.Integer, primary_key=True)
    tradingsymbol = db.Column(db.String(50), unique=True, nullable=False, index=True)

    # Market Cap data
    total_market_cap = db.Column(db.Float, nullable=True)  # Total Market Cap in crores
    free_float_market_cap = db.Column(db.Float, nullable=True)  # Free Float Market Cap in crores

    # Stock price and shares data
    last_traded_price = db.Column(db.Float, nullable=True)  # Last traded price (LTP)
    outstanding_shares = db.Column(db.BigInteger, nullable=True)  # Total outstanding shares
    float_shares = db.Column(db.BigInteger, nullable=True)  # Float shares (publicly tradable shares)

    # Additional metadata
    company_name = db.Column(db.String(200), nullable=True)
    last_updated = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<StockInformation {self.tradingsymbol} TotalMC:{self.total_market_cap}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'tradingsymbol': self.tradingsymbol,
            'company_name': self.company_name,
            'total_market_cap': self.total_market_cap,
            'free_float_market_cap': self.free_float_market_cap,
            'last_traded_price': self.last_traded_price,
            'outstanding_shares': self.outstanding_shares,
            'float_shares': self.float_shares,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class MarketCapFetchTask(db.Model):
    """Model for tracking market cap data fetch tasks"""

    __tablename__ = 'marketcap_fetch_tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Progress tracking
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    progress_percentage = db.Column(db.Float, default=0.0)
    total_stocks = db.Column(db.Integer, default=0)
    completed_stocks = db.Column(db.Integer, default=0)
    failed_stocks = db.Column(db.Integer, default=0)
    current_stock_symbol = db.Column(db.String(50), nullable=True)

    # Statistics
    total_api_calls = db.Column(db.Integer, default=0)
    total_success = db.Column(db.Integer, default=0)

    # Failed stocks tracking (JSON array of symbols)
    failed_stocks_list = db.Column(db.Text, nullable=True)  # JSON array of failed symbols

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Error handling
    error_message = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('marketcap_fetch_tasks', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<MarketCapFetchTask {self.id} User:{self.user_id} Status:{self.status} Progress:{self.progress_percentage}%>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        import json
        failed_list = []
        if self.failed_stocks_list:
            try:
                failed_list = json.loads(self.failed_stocks_list)
            except:
                failed_list = []

        return {
            'id': self.id,
            'status': self.status,
            'progress_percentage': round(self.progress_percentage, 2),
            'total_stocks': self.total_stocks,
            'completed_stocks': self.completed_stocks,
            'failed_stocks': self.failed_stocks,
            'current_stock_symbol': self.current_stock_symbol,
            'total_api_calls': self.total_api_calls,
            'total_success': self.total_success,
            'failed_stocks_list': failed_list,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message
        }


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))
