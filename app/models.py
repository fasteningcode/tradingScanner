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
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

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
    index_symbol = db.Column(db.String(10), unique=True, nullable=True, index=True)  # Short index symbol (e.g., "BNK-IDX")
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(50), nullable=True)  # Bootstrap icon class
    color = db.Column(db.String(20), nullable=True)  # Color for visualization
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)

    # Stage Analysis fields
    current_stage = db.Column(db.Integer, nullable=True, index=True)  # 1-4 (Weinstein stages)
    stage_updated_at = db.Column(db.DateTime, nullable=True)  # When stage was last calculated
    stage_confidence = db.Column(db.Float, nullable=True)  # 0-100 confidence score

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
            'current_stage': self.current_stage,
            'stage_updated_at': self.stage_updated_at.isoformat() if self.stage_updated_at else None,
            'stage_confidence': self.stage_confidence,
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
    index_symbol = db.Column(db.String(10), unique=True, nullable=True, index=True)  # Short index symbol (e.g., "BNK-PVT")
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)

    # Stage Analysis fields
    current_stage = db.Column(db.Integer, nullable=True, index=True)  # 1-4 (Weinstein stages)
    stage_updated_at = db.Column(db.DateTime, nullable=True)  # When stage was last calculated
    stage_confidence = db.Column(db.Float, nullable=True)  # 0-100 confidence score

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
            'current_stage': self.current_stage,
            'stage_updated_at': self.stage_updated_at.isoformat() if self.stage_updated_at else None,
            'stage_confidence': self.stage_confidence,
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

    # Stock Stage Analysis fields
    current_stage = db.Column(db.Integer, nullable=True, index=True)  # 1-4 (Weinstein stages)
    stage_updated_at = db.Column(db.DateTime, nullable=True)  # When stage was last calculated
    stage_confidence = db.Column(db.Float, nullable=True)  # 0-100 confidence score

    # Relative Strength (RS) fields
    rs_vs_subsector = db.Column(db.Float, nullable=True, index=True)  # RS relative to subsector index
    rs_vs_sector = db.Column(db.Float, nullable=True, index=True)  # RS relative to sector index
    rs_base_date = db.Column(db.Date, nullable=True)  # Base date used for RS calculation
    rs_updated_at = db.Column(db.DateTime, nullable=True)  # When RS was last calculated

    # Volume Dry-Up Analysis fields
    volume_dryup_status = db.Column(db.String(20), nullable=True, index=True)  # 'qualified', 'not_qualified', null
    volume_ratio_pct = db.Column(db.Float, nullable=True, index=True)  # Current volume as % of 20-day avg
    consolidation_5d_pct = db.Column(db.Float, nullable=True)  # 5-day price consolidation range %
    volume_dryup_updated_at = db.Column(db.DateTime, nullable=True)  # When analysis was last run
    volume_dryup_classification = db.Column(db.String(20), nullable=True)  # 'extreme', 'strong', 'good', 'moderate'
    volume_declining_days = db.Column(db.Integer, nullable=True)  # Count of declining volume days (out of 9)

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

    # Incremental sync configuration
    sync_mode = db.Column(db.String(20), default='full')  # 'full', 'incremental', 'gap_fill'
    target_stocks = db.Column(db.Text, nullable=True)  # JSON array of specific symbols to sync (optional)
    auto_calculate_index = db.Column(db.Boolean, default=False)  # Auto-trigger index calculation after sync

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
            'error_count': self.error_count,
            'sync_mode': self.sync_mode,
            'target_stocks': self.target_stocks,
            'auto_calculate_index': self.auto_calculate_index
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


class SyncTask(db.Model):
    """Model for tracking incremental historical data sync tasks"""

    __tablename__ = 'sync_tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Task configuration
    interval = db.Column(db.String(20), nullable=False)  # Candle interval being synced

    # Progress tracking
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    progress_percentage = db.Column(db.Float, default=0.0)
    total_stocks = db.Column(db.Integer, default=0)
    synced_stocks = db.Column(db.Integer, default=0)
    failed_stocks = db.Column(db.Integer, default=0)
    skipped_stocks = db.Column(db.Integer, default=0)  # Already up to date
    new_candles_added = db.Column(db.Integer, default=0)  # Total new candles added across all stocks

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Error handling
    error_message = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('sync_tasks', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<SyncTask {self.id} User:{self.user_id} Status:{self.status} Progress:{self.progress_percentage}%>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        # Calculate progress
        if self.total_stocks > 0:
            self.progress_percentage = (self.synced_stocks / self.total_stocks) * 100
        else:
            self.progress_percentage = 0.0

        # Calculate ETA
        eta_seconds = None
        if self.status == 'running' and self.started_at and self.synced_stocks > 0:
            elapsed = (datetime.utcnow() - self.started_at).total_seconds()
            avg_time_per_stock = elapsed / self.synced_stocks
            remaining_stocks = self.total_stocks - self.synced_stocks
            eta_seconds = int(remaining_stocks * avg_time_per_stock)

        return {
            'id': self.id,
            'user_id': self.user_id,
            'status': self.status,
            'progress_percentage': round(self.progress_percentage, 2),
            'total_stocks': self.total_stocks,
            'synced_stocks': self.synced_stocks,
            'failed_stocks': self.failed_stocks,
            'skipped_stocks': self.skipped_stocks,
            'new_candles_added': self.new_candles_added,
            'interval': self.interval,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'error_message': self.error_message,
            'eta_seconds': eta_seconds
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


class StageAnalysisTask(db.Model):
    """Model for tracking stage analysis tasks"""

    __tablename__ = 'stage_analysis_tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Progress tracking
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    progress_percentage = db.Column(db.Float, default=0.0)
    total_symbols = db.Column(db.Integer, default=0)  # Total sectors + subsectors
    analyzed_symbols = db.Column(db.Integer, default=0)
    failed_symbols = db.Column(db.Integer, default=0)
    current_symbol = db.Column(db.String(50), nullable=True)

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Error handling
    error_message = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('stage_analysis_tasks', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<StageAnalysisTask {self.id} User:{self.user_id} Status:{self.status}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        # Calculate ETA if running
        eta_seconds = None
        if self.status == 'running' and self.analyzed_symbols > 0 and self.started_at:
            elapsed = (datetime.utcnow() - self.started_at).total_seconds()
            avg_time_per_symbol = elapsed / self.analyzed_symbols
            remaining_symbols = self.total_symbols - self.analyzed_symbols
            eta_seconds = int(avg_time_per_symbol * remaining_symbols)

        return {
            'id': self.id,
            'status': self.status,
            'progress_percentage': round(self.progress_percentage, 2),
            'total_symbols': self.total_symbols,
            'analyzed_symbols': self.analyzed_symbols,
            'failed_symbols': self.failed_symbols,
            'current_symbol': self.current_symbol,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'eta_seconds': eta_seconds
        }


class StageAnalysisHistory(db.Model):
    """Model for storing historical stage analysis results"""

    __tablename__ = 'stage_analysis_history'

    id = db.Column(db.Integer, primary_key=True)
    index_symbol = db.Column(db.String(10), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    stage = db.Column(db.Integer, nullable=False)  # 1-4
    stage_confidence = db.Column(db.Float, nullable=True)  # 0-100
    moving_avg_30 = db.Column(db.Float, nullable=True)
    moving_avg_150 = db.Column(db.Float, nullable=True)
    current_price = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Unique constraint: one stage analysis per symbol per date
    __table_args__ = (
        db.UniqueConstraint('index_symbol', 'date', name='uq_stage_symbol_date'),
        db.Index('idx_stage_lookup', 'index_symbol', 'date'),
    )

    def __repr__(self):
        return f'<StageAnalysisHistory {self.index_symbol} {self.date} Stage:{self.stage}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'index_symbol': self.index_symbol,
            'date': self.date.isoformat() if self.date else None,
            'stage': self.stage,
            'stage_confidence': self.stage_confidence,
            'moving_avg_30': self.moving_avg_30,
            'moving_avg_150': self.moving_avg_150,
            'current_price': self.current_price,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class StockStageAnalysisTask(db.Model):
    """Model for tracking stock stage analysis tasks"""

    __tablename__ = 'stock_stage_analysis_tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Filter configuration
    filter_type = db.Column(db.String(20), default='nifty500', nullable=False)  # 'nifty500', 'all', 'sector', 'subsector'
    sector_id = db.Column(db.Integer, db.ForeignKey('sectors.id'), nullable=True, index=True)
    subsector_id = db.Column(db.Integer, db.ForeignKey('sub_sectors.id'), nullable=True, index=True)

    # Progress tracking
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    progress_percentage = db.Column(db.Float, default=0.0)
    total_stocks = db.Column(db.Integer, default=0)
    analyzed_stocks = db.Column(db.Integer, default=0)
    failed_stocks = db.Column(db.Integer, default=0)
    skipped_stocks = db.Column(db.Integer, default=0)  # Insufficient data
    current_stock_symbol = db.Column(db.String(50), nullable=True)

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Error handling
    error_message = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('stock_stage_analysis_tasks', lazy='dynamic', cascade='all, delete-orphan'))
    sector = db.relationship('Sector', foreign_keys=[sector_id])
    subsector = db.relationship('SubSector', foreign_keys=[subsector_id])

    def __repr__(self):
        return f'<StockStageAnalysisTask {self.id} User:{self.user_id} Status:{self.status}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        # Calculate ETA if running
        eta_seconds = None
        if self.status == 'running' and self.analyzed_stocks > 0 and self.started_at:
            elapsed = (datetime.utcnow() - self.started_at).total_seconds()
            avg_time_per_stock = elapsed / self.analyzed_stocks
            remaining_stocks = self.total_stocks - self.analyzed_stocks
            eta_seconds = int(avg_time_per_stock * remaining_stocks)

        return {
            'id': self.id,
            'filter_type': self.filter_type,
            'sector_id': self.sector_id,
            'subsector_id': self.subsector_id,
            'status': self.status,
            'progress_percentage': round(self.progress_percentage, 2),
            'total_stocks': self.total_stocks,
            'analyzed_stocks': self.analyzed_stocks,
            'failed_stocks': self.failed_stocks,
            'skipped_stocks': self.skipped_stocks,
            'current_stock_symbol': self.current_stock_symbol,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'eta_seconds': eta_seconds
        }


class RSCalculationTask(db.Model):
    """Model for tracking Relative Strength calculation tasks"""

    __tablename__ = 'rs_calculation_tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # RS Configuration
    base_date = db.Column(db.Date, nullable=False)  # Base date for RS calculation

    # Progress tracking
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    progress_percentage = db.Column(db.Float, default=0.0)
    total_stocks = db.Column(db.Integer, default=0)
    processed_stocks = db.Column(db.Integer, default=0)
    failed_stocks = db.Column(db.Integer, default=0)
    skipped_stocks = db.Column(db.Integer, default=0)  # Missing data or no sector assignment
    current_stock_symbol = db.Column(db.String(50), nullable=True)

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Error handling
    error_message = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('rs_calculation_tasks', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<RSCalculationTask {self.id} User:{self.user_id} Status:{self.status}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        # Calculate ETA if running
        eta_seconds = None
        if self.status == 'running' and self.processed_stocks > 0 and self.started_at:
            elapsed = (datetime.utcnow() - self.started_at).total_seconds()
            avg_time_per_stock = elapsed / self.processed_stocks
            remaining_stocks = self.total_stocks - self.processed_stocks
            eta_seconds = int(avg_time_per_stock * remaining_stocks)

        return {
            'id': self.id,
            'base_date': self.base_date.isoformat() if self.base_date else None,
            'status': self.status,
            'progress_percentage': round(self.progress_percentage, 2),
            'total_stocks': self.total_stocks,
            'processed_stocks': self.processed_stocks,
            'failed_stocks': self.failed_stocks,
            'skipped_stocks': self.skipped_stocks,
            'current_stock_symbol': self.current_stock_symbol,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'eta_seconds': eta_seconds
        }


class SectorIndex(db.Model):
    """Model for storing calculated sector/subsector indices"""

    __tablename__ = 'sector_indices'

    id = db.Column(db.Integer, primary_key=True)

    # Index type and reference
    index_type = db.Column(db.String(20), nullable=False, index=True)  # 'market', 'sector', 'subsector'
    sector_id = db.Column(db.Integer, db.ForeignKey('sectors.id'), nullable=True, index=True)
    subsector_id = db.Column(db.Integer, db.ForeignKey('sub_sectors.id'), nullable=True, index=True)

    # Index values
    index_value = db.Column(db.Float, nullable=False)  # Calculated index value
    total_market_cap = db.Column(db.Float, nullable=True)  # Total market cap (in crores)
    stock_count = db.Column(db.Integer, nullable=True)  # Number of stocks in index

    # Change tracking (optional - for future use with historical data)
    change_1d = db.Column(db.Float, nullable=True)  # 1-day change percentage
    change_1w = db.Column(db.Float, nullable=True)  # 1-week change percentage
    change_1m = db.Column(db.Float, nullable=True)  # 1-month change percentage

    # Timestamps
    calculated_at = db.Column(db.DateTime, nullable=False, index=True)  # When index was calculated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sector = db.relationship('Sector', foreign_keys=[sector_id], backref=db.backref('indices', lazy='dynamic'))
    subsector = db.relationship('SubSector', foreign_keys=[subsector_id], backref=db.backref('indices', lazy='dynamic'))

    # Add unique constraint for each index type
    __table_args__ = (
        db.Index('idx_sector_index_type', 'index_type', 'sector_id', 'subsector_id'),
    )

    def __repr__(self):
        if self.index_type == 'market':
            return f'<SectorIndex Market value={self.index_value:.2f}>'
        elif self.index_type == 'sector':
            return f'<SectorIndex Sector:{self.sector_id} value={self.index_value:.2f}>'
        else:
            return f'<SectorIndex SubSector:{self.subsector_id} value={self.index_value:.2f}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'index_type': self.index_type,
            'sector_id': self.sector_id,
            'subsector_id': self.subsector_id,
            'index_value': self.index_value,
            'total_market_cap': self.total_market_cap,
            'stock_count': self.stock_count,
            'change_1d': self.change_1d,
            'change_1w': self.change_1w,
            'change_1m': self.change_1m,
            'calculated_at': self.calculated_at.isoformat() if self.calculated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class IndexHistory(db.Model):
    """Model for storing daily historical index values"""

    __tablename__ = 'index_history'

    id = db.Column(db.Integer, primary_key=True)
    index_symbol = db.Column(db.String(10), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    index_value = db.Column(db.Float, nullable=False)
    index_calculated_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint: no duplicate calculations for same (symbol, date)
    __table_args__ = (
        db.UniqueConstraint('index_symbol', 'date', name='uq_index_symbol_date'),
        db.Index('idx_index_history_lookup', 'index_symbol', 'date'),
    )

    def __repr__(self):
        return f'<IndexHistory {self.index_symbol} {self.date} value={self.index_value:.2f}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'index_symbol': self.index_symbol,
            'date': self.date.isoformat() if self.date else None,
            'index_value': self.index_value,
            'index_calculated_date': self.index_calculated_date.isoformat() if self.index_calculated_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ScannerProfile(db.Model):
    """Scanner profiles for saving scan configurations"""

    __tablename__ = 'scanner_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    criteria = db.Column(db.Text, nullable=True)  # JSON string for scan criteria (to be defined later)
    is_default = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('scanner_profiles', lazy='dynamic', cascade='all, delete-orphan'))
    scan_tasks = db.relationship('ScannerTask', back_populates='profile', cascade='all, delete-orphan')

    # Table constraints
    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='uq_user_profile_name'),
        db.Index('idx_profile_lookup', 'user_id', 'is_default'),
    )

    def __repr__(self):
        return f'<ScannerProfile {self.name} User:{self.user_id}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'criteria': self.criteria,
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ScannerTask(db.Model):
    """Model for tracking scanner task execution"""

    __tablename__ = 'scanner_tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('scanner_profiles.id'), nullable=True, index=True)

    # Progress tracking
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    progress_percentage = db.Column(db.Float, default=0.0)
    progress_message = db.Column(db.Text, nullable=True)  # Current status message for UI display
    total_stocks = db.Column(db.Integer, default=0)
    scanned_stocks = db.Column(db.Integer, default=0)
    matched_stocks = db.Column(db.Integer, default=0)  # Stocks that passed the criteria
    failed_stocks = db.Column(db.Integer, default=0)
    current_stock_symbol = db.Column(db.String(50), nullable=True)

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Error handling
    error_message = db.Column(db.Text, nullable=True)

    # Criteria snapshot (stores the exact criteria used for this scan)
    criteria_snapshot = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('scanner_tasks', lazy='dynamic', cascade='all, delete-orphan'))
    profile = db.relationship('ScannerProfile', back_populates='scan_tasks')

    def __repr__(self):
        return f'<ScannerTask {self.id} User:{self.user_id} Status:{self.status}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        # Calculate ETA if running
        eta_seconds = None
        if self.status == 'running' and self.scanned_stocks > 0 and self.started_at:
            elapsed = (datetime.utcnow() - self.started_at).total_seconds()
            avg_time_per_stock = elapsed / self.scanned_stocks
            remaining_stocks = self.total_stocks - self.scanned_stocks
            eta_seconds = int(avg_time_per_stock * remaining_stocks)

        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'status': self.status,
            'progress_percentage': round(self.progress_percentage, 2),
            'progress_message': self.progress_message,
            'total_stocks': self.total_stocks,
            'scanned_stocks': self.scanned_stocks,
            'matched_stocks': self.matched_stocks,
            'failed_stocks': self.failed_stocks,
            'current_stock_symbol': self.current_stock_symbol,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'eta_seconds': eta_seconds
        }


class ScanResultStock(db.Model):
    """Model for storing individual stock results from scanner execution"""

    __tablename__ = 'scan_result_stocks'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('scanner_tasks.id'), nullable=False, index=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=False, index=True)
    tradingsymbol = db.Column(db.String(50), nullable=False, index=True)

    # Current metrics at scan time
    current_price = db.Column(db.Float)
    stage = db.Column(db.Integer)
    sector_name = db.Column(db.String(100))
    subsector_name = db.Column(db.String(100))

    # RS metrics
    rs_vs_subsector = db.Column(db.Float)
    rs_vs_sector = db.Column(db.Float)

    # Volume metrics
    volume_dryup_status = db.Column(db.String(50))
    volume_dryup_classification = db.Column(db.String(50))
    volume_ratio_pct = db.Column(db.Float)

    # Moving averages (JSON array of MAs stock is above)
    ma_above = db.Column(db.Text)  # e.g., '["SMA_50", "EMA_20"]'

    # Price action pattern
    price_action_pattern = db.Column(db.String(50))  # 'breakout', 'pullback', or null

    # Scan ranking (for sorting)
    scan_rank = db.Column(db.Integer, index=True)
    scan_score = db.Column(db.Float)  # Calculated score used for ranking

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    task = db.relationship('ScannerTask', backref=db.backref('stock_results', lazy='dynamic', cascade='all, delete-orphan'))
    instrument = db.relationship('Instrument')

    def __repr__(self):
        return f'<ScanResultStock {self.id} Task:{self.task_id} Symbol:{self.tradingsymbol} Rank:{self.scan_rank}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        import json
        ma_list = []
        if self.ma_above:
            try:
                ma_list = json.loads(self.ma_above)
            except:
                ma_list = []

        return {
            'id': self.id,
            'task_id': self.task_id,
            'tradingsymbol': self.tradingsymbol,
            'current_price': self.current_price,
            'stage': self.stage,
            'sector_name': self.sector_name,
            'subsector_name': self.subsector_name,
            'rs_vs_subsector': round(self.rs_vs_subsector, 2) if self.rs_vs_subsector else None,
            'rs_vs_sector': round(self.rs_vs_sector, 2) if self.rs_vs_sector else None,
            'volume_dryup_status': self.volume_dryup_status,
            'volume_dryup_classification': self.volume_dryup_classification,
            'volume_ratio_pct': round(self.volume_ratio_pct, 2) if self.volume_ratio_pct else None,
            'ma_above': ma_list,
            'price_action_pattern': self.price_action_pattern,
            'scan_rank': self.scan_rank,
            'scan_score': round(self.scan_score, 2) if self.scan_score else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class VolumeDryUpTask(db.Model):
    """Model for tracking volume dry-up analysis tasks"""

    __tablename__ = 'volume_dryup_tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Configuration
    min_volume_pct = db.Column(db.Float, default=50.0, nullable=False)  # Volume must be < this % of 20-day avg
    max_consolidation_pct = db.Column(db.Float, default=6.0, nullable=False)  # 5-day range must be < this %

    # Progress tracking
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    progress_percentage = db.Column(db.Float, default=0.0)
    total_stocks = db.Column(db.Integer, default=0)
    analyzed_stocks = db.Column(db.Integer, default=0)
    qualified_stocks = db.Column(db.Integer, default=0)  # Stocks that passed both criteria
    failed_stocks = db.Column(db.Integer, default=0)
    current_stock_symbol = db.Column(db.String(50), nullable=True)

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Error handling
    error_message = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('volume_dryup_tasks', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<VolumeDryUpTask {self.id} User:{self.user_id} Status:{self.status}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        # Calculate ETA if running
        eta_seconds = None
        if self.status == 'running' and self.analyzed_stocks > 0 and self.started_at:
            elapsed = (datetime.utcnow() - self.started_at).total_seconds()
            avg_time_per_stock = elapsed / self.analyzed_stocks
            remaining_stocks = self.total_stocks - self.analyzed_stocks
            eta_seconds = int(avg_time_per_stock * remaining_stocks)

        return {
            'id': self.id,
            'min_volume_pct': self.min_volume_pct,
            'max_consolidation_pct': self.max_consolidation_pct,
            'status': self.status,
            'progress_percentage': round(self.progress_percentage, 2),
            'total_stocks': self.total_stocks,
            'analyzed_stocks': self.analyzed_stocks,
            'qualified_stocks': self.qualified_stocks,
            'failed_stocks': self.failed_stocks,
            'current_stock_symbol': self.current_stock_symbol,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'eta_seconds': eta_seconds
        }


class MasterSyncTask(db.Model):
    """Model for tracking master synchronization tasks that orchestrate multiple analysis steps"""

    __tablename__ = 'master_sync_tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Progress tracking
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    progress_percentage = db.Column(db.Float, default=0.0)
    current_step = db.Column(db.Integer, default=0)  # 0-7 (0=not started, 1-7=step number)
    current_step_name = db.Column(db.String(100), nullable=True)
    total_steps = db.Column(db.Integer, default=7)

    # Sub-task IDs (links to individual task tables)
    download_task_id = db.Column(db.Integer, db.ForeignKey('download_tasks.id'), nullable=True)
    sync_task_id = db.Column(db.Integer, db.ForeignKey('sync_tasks.id'), nullable=True)
    marketcap_task_id = db.Column(db.Integer, db.ForeignKey('marketcap_fetch_tasks.id'), nullable=True)
    stage_analysis_task_id = db.Column(db.Integer, db.ForeignKey('stage_analysis_tasks.id'), nullable=True)
    stock_stage_task_id = db.Column(db.Integer, db.ForeignKey('stock_stage_analysis_tasks.id'), nullable=True)
    rs_calculation_task_id = db.Column(db.Integer, db.ForeignKey('rs_calculation_tasks.id'), nullable=True)
    volume_dryup_task_id = db.Column(db.Integer, db.ForeignKey('volume_dryup_tasks.id'), nullable=True)

    # Step details (JSON) - stores status and progress of each step
    step_details = db.Column(db.Text, nullable=True)  # JSON: {"1": {"status": "completed", "progress": 100}, ...}

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Error handling
    error_message = db.Column(db.Text, nullable=True)
    error_details = db.Column(db.Text, nullable=True)  # JSON: {"step_3": "Index generation failed: ...", ...}

    # Relationships
    user = db.relationship('User', backref=db.backref('master_sync_tasks', lazy='dynamic', cascade='all, delete-orphan'))
    download_task = db.relationship('DownloadTask', foreign_keys=[download_task_id], backref='master_sync_tasks')
    sync_task = db.relationship('SyncTask', foreign_keys=[sync_task_id], backref='master_sync_tasks')
    marketcap_task = db.relationship('MarketCapFetchTask', foreign_keys=[marketcap_task_id], backref='master_sync_tasks')
    stage_analysis_task = db.relationship('StageAnalysisTask', foreign_keys=[stage_analysis_task_id], backref='master_sync_tasks')
    stock_stage_task = db.relationship('StockStageAnalysisTask', foreign_keys=[stock_stage_task_id], backref='master_sync_tasks')
    rs_calculation_task = db.relationship('RSCalculationTask', foreign_keys=[rs_calculation_task_id], backref='master_sync_tasks')
    volume_dryup_task = db.relationship('VolumeDryUpTask', foreign_keys=[volume_dryup_task_id], backref='master_sync_tasks')

    def __repr__(self):
        return f'<MasterSyncTask {self.id} User:{self.user_id} Status:{self.status} Step:{self.current_step}/{self.total_steps}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        import json

        # Parse step_details and error_details if they exist
        step_details_dict = {}
        error_details_dict = {}

        if self.step_details:
            try:
                step_details_dict = json.loads(self.step_details)
            except:
                pass

        if self.error_details:
            try:
                error_details_dict = json.loads(self.error_details)
            except:
                pass

        # Calculate ETA if running
        eta_seconds = None
        if self.status == 'running' and self.current_step > 0 and self.started_at:
            elapsed = (datetime.utcnow() - self.started_at).total_seconds()
            avg_time_per_step = elapsed / self.current_step
            remaining_steps = self.total_steps - self.current_step
            eta_seconds = int(avg_time_per_step * remaining_steps)

        return {
            'id': self.id,
            'user_id': self.user_id,
            'status': self.status,
            'progress_percentage': round(self.progress_percentage, 2),
            'current_step': self.current_step,
            'current_step_name': self.current_step_name,
            'total_steps': self.total_steps,
            'step_details': step_details_dict,
            'error_details': error_details_dict,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'error_message': self.error_message,
            'eta_seconds': eta_seconds,
            'subtask_ids': {
                'download_task_id': self.download_task_id,
                'sync_task_id': self.sync_task_id,
                'marketcap_task_id': self.marketcap_task_id,
                'stage_analysis_task_id': self.stage_analysis_task_id,
                'stock_stage_task_id': self.stock_stage_task_id,
                'rs_calculation_task_id': self.rs_calculation_task_id,
                'volume_dryup_task_id': self.volume_dryup_task_id
            }
        }


class AlignedBreakoutProfile(db.Model):
    """Configuration for Aligned Breakout Strategy scanner profiles"""

    __tablename__ = 'aligned_breakout_profiles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # Sector Alignment Criteria
    sector_stage = db.Column(db.Integer, default=2)  # Required sector stage
    sector_max_weeks_in_stage = db.Column(db.Integer, default=24)  # < 6 months = 24 weeks
    sector_rs_min = db.Column(db.Float, default=60.0)  # Sector RS vs Nifty 50 > 60
    subsector_rs_min = db.Column(db.Float, default=60.0)  # SubSector RS vs Nifty 50 > 60

    # Stock Stage Criteria
    stock_stage = db.Column(db.Integer, default=2)  # Required stock stage
    stock_max_weeks_in_stage = db.Column(db.Integer, default=4)  # Early Stage 2 < 4 weeks
    price_above_150ma = db.Column(db.Boolean, default=True)  # Price must be > 150-day MA
    ma_150_slope_min = db.Column(db.Float, default=0.0)  # 150-day MA trending up (slope > 0)
    distance_from_52w_high_min = db.Column(db.Float, default=10.0)  # 10% from 52-week high
    distance_from_52w_high_max = db.Column(db.Float, default=30.0)  # 30% from 52-week high

    # Volume Confirmation Criteria
    breakout_volume_min_pct = db.Column(db.Float, default=150.0)  # Breakout volume > 150% of 50-day avg
    accumulation_days = db.Column(db.Integer, default=3)  # Volume increasing for 3 days

    # Relative Strength Criteria
    stock_rs_vs_sector_min = db.Column(db.Float, default=70.0)  # Stock RS vs Sector > 70
    stock_rs_vs_subsector_min = db.Column(db.Float, default=70.0)  # Stock RS vs SubSector > 70
    stock_rs_vs_nifty50_min = db.Column(db.Float, default=65.0)  # Stock RS vs Nifty 50 > 65
    rs_trend_weeks = db.Column(db.Integer, default=4)  # RS trend over 4 weeks
    rs_trend_direction = db.Column(db.String(20), default='improving')  # 'improving', 'stable', 'any'

    # Scoring Weights (optional)
    weight_sector_alignment = db.Column(db.Float, default=25.0)
    weight_stock_stage = db.Column(db.Float, default=25.0)
    weight_volume = db.Column(db.Float, default=25.0)
    weight_rs = db.Column(db.Float, default=25.0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    scan_results = db.relationship('AlignedBreakoutScanResult', back_populates='profile', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<AlignedBreakoutProfile {self.name}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'sector_stage': self.sector_stage,
            'sector_max_weeks_in_stage': self.sector_max_weeks_in_stage,
            'sector_rs_min': self.sector_rs_min,
            'subsector_rs_min': self.subsector_rs_min,
            'stock_stage': self.stock_stage,
            'stock_max_weeks_in_stage': self.stock_max_weeks_in_stage,
            'price_above_150ma': self.price_above_150ma,
            'ma_150_slope_min': self.ma_150_slope_min,
            'distance_from_52w_high_min': self.distance_from_52w_high_min,
            'distance_from_52w_high_max': self.distance_from_52w_high_max,
            'breakout_volume_min_pct': self.breakout_volume_min_pct,
            'accumulation_days': self.accumulation_days,
            'stock_rs_vs_sector_min': self.stock_rs_vs_sector_min,
            'stock_rs_vs_subsector_min': self.stock_rs_vs_subsector_min,
            'stock_rs_vs_nifty50_min': self.stock_rs_vs_nifty50_min,
            'rs_trend_weeks': self.rs_trend_weeks,
            'rs_trend_direction': self.rs_trend_direction,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class AlignedBreakoutScanResult(db.Model):
    """Historical scan execution results for Aligned Breakout Strategy"""

    __tablename__ = 'aligned_breakout_scan_results'

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('aligned_breakout_profiles.id'), nullable=False, index=True)

    # Scan execution tracking
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # 'pending', 'running', 'completed', 'failed'
    total_stocks_scanned = db.Column(db.Integer, default=0)
    matched_stocks = db.Column(db.Integer, default=0)

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Error handling
    error_message = db.Column(db.Text, nullable=True)

    # Relationships
    profile = db.relationship('AlignedBreakoutProfile', back_populates='scan_results')

    def __repr__(self):
        return f'<AlignedBreakoutScanResult Profile:{self.profile_id} Matched:{self.matched_stocks}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'status': self.status,
            'total_stocks_scanned': self.total_stocks_scanned,
            'matched_stocks': self.matched_stocks,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message
        }


class AlignedBreakoutStockMetrics(db.Model):
    """Extended stock metrics for Aligned Breakout Strategy"""

    __tablename__ = 'aligned_breakout_stock_metrics'

    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=False, unique=True, index=True)

    # 52-week tracking
    week_52_high = db.Column(db.Float, nullable=True)
    week_52_low = db.Column(db.Float, nullable=True)
    week_52_high_date = db.Column(db.Date, nullable=True)
    week_52_low_date = db.Column(db.Date, nullable=True)
    distance_from_52w_high_pct = db.Column(db.Float, nullable=True, index=True)  # % below 52-week high

    # Moving Average values and slopes
    ma_150_value = db.Column(db.Float, nullable=True)
    ma_150_slope = db.Column(db.Float, nullable=True, index=True)  # Slope of 150-day MA (positive = trending up)

    # RS vs Nifty 50
    rs_vs_nifty50 = db.Column(db.Float, nullable=True, index=True)
    rs_vs_nifty50_trend = db.Column(db.String(20), nullable=True)  # 'improving', 'stable', 'declining'

    # Time in stage tracking
    current_stage = db.Column(db.Integer, nullable=True, index=True)
    stage_entry_date = db.Column(db.Date, nullable=True)
    weeks_in_stage = db.Column(db.Integer, nullable=True, index=True)

    # Volume metrics
    avg_volume_50d = db.Column(db.BigInteger, nullable=True)
    last_volume = db.Column(db.BigInteger, nullable=True)
    volume_breakout_detected = db.Column(db.Boolean, default=False, index=True)
    accumulation_pattern_days = db.Column(db.Integer, default=0)  # Consecutive days of volume increase

    # Last update
    calculated_at = db.Column(db.DateTime, nullable=True, index=True)

    # Relationships
    instrument = db.relationship('Instrument', backref=db.backref('aligned_breakout_metrics', uselist=False))

    def __repr__(self):
        return f'<AlignedBreakoutStockMetrics {self.instrument_id} Stage:{self.current_stage}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'instrument_id': self.instrument_id,
            'week_52_high': self.week_52_high,
            'week_52_low': self.week_52_low,
            'distance_from_52w_high_pct': self.distance_from_52w_high_pct,
            'ma_150_value': self.ma_150_value,
            'ma_150_slope': self.ma_150_slope,
            'rs_vs_nifty50': self.rs_vs_nifty50,
            'rs_vs_nifty50_trend': self.rs_vs_nifty50_trend,
            'current_stage': self.current_stage,
            'weeks_in_stage': self.weeks_in_stage,
            'volume_breakout_detected': self.volume_breakout_detected,
            'accumulation_pattern_days': self.accumulation_pattern_days,
            'calculated_at': self.calculated_at.isoformat() if self.calculated_at else None
        }


class AlignedBreakoutSectorMetrics(db.Model):
    """Sector/SubSector metrics for Aligned Breakout Strategy"""

    __tablename__ = 'aligned_breakout_sector_metrics'

    id = db.Column(db.Integer, primary_key=True)

    # Entity type and reference
    entity_type = db.Column(db.String(20), nullable=False, index=True)  # 'sector' or 'subsector'
    sector_id = db.Column(db.Integer, db.ForeignKey('sectors.id'), nullable=True, index=True)
    subsector_id = db.Column(db.Integer, db.ForeignKey('sub_sectors.id'), nullable=True, index=True)

    # RS vs Nifty 50
    rs_vs_nifty50 = db.Column(db.Float, nullable=True, index=True)
    rs_vs_nifty50_trend = db.Column(db.String(20), nullable=True)  # 'improving', 'stable', 'declining'

    # Stage tracking
    current_stage = db.Column(db.Integer, nullable=True, index=True)
    stage_entry_date = db.Column(db.Date, nullable=True)
    weeks_in_stage = db.Column(db.Integer, nullable=True, index=True)

    # Last update
    calculated_at = db.Column(db.DateTime, nullable=True, index=True)

    # Relationships
    sector = db.relationship('Sector', foreign_keys=[sector_id], backref=db.backref('aligned_breakout_metrics', lazy='dynamic'))
    subsector = db.relationship('SubSector', foreign_keys=[subsector_id], backref=db.backref('aligned_breakout_metrics', lazy='dynamic'))

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('entity_type', 'sector_id', 'subsector_id', name='uq_entity_sector_subsector'),
        db.Index('idx_entity_lookup', 'entity_type', 'sector_id', 'subsector_id'),
    )

    def __repr__(self):
        if self.entity_type == 'sector':
            return f'<AlignedBreakoutSectorMetrics Sector:{self.sector_id} Stage:{self.current_stage}>'
        else:
            return f'<AlignedBreakoutSectorMetrics SubSector:{self.subsector_id} Stage:{self.current_stage}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'entity_type': self.entity_type,
            'sector_id': self.sector_id,
            'subsector_id': self.subsector_id,
            'rs_vs_nifty50': self.rs_vs_nifty50,
            'rs_vs_nifty50_trend': self.rs_vs_nifty50_trend,
            'current_stage': self.current_stage,
            'weeks_in_stage': self.weeks_in_stage,
            'calculated_at': self.calculated_at.isoformat() if self.calculated_at else None
        }


class AlignedBreakoutWatchlist(db.Model):
    """Denormalized watchlist for fast querying of matched stocks"""

    __tablename__ = 'aligned_breakout_watchlist'

    id = db.Column(db.Integer, primary_key=True)
    scan_result_id = db.Column(db.Integer, db.ForeignKey('aligned_breakout_scan_results.id'), nullable=False, index=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=False, index=True)

    # Denormalized stock info for fast access
    tradingsymbol = db.Column(db.String(50), nullable=False, index=True)
    sector_name = db.Column(db.String(100), nullable=True)
    subsector_name = db.Column(db.String(100), nullable=True)

    # Criteria scores (0-100 for each category)
    score_sector_alignment = db.Column(db.Float, default=0.0)
    score_stock_stage = db.Column(db.Float, default=0.0)
    score_volume = db.Column(db.Float, default=0.0)
    score_rs = db.Column(db.Float, default=0.0)
    score_total = db.Column(db.Float, default=0.0, index=True)  # Weighted total score

    # Snapshot of key metrics at scan time
    current_price = db.Column(db.Float, nullable=True)
    distance_from_52w_high_pct = db.Column(db.Float, nullable=True)
    rs_vs_nifty50 = db.Column(db.Float, nullable=True)
    rs_vs_sector = db.Column(db.Float, nullable=True)
    rs_vs_subsector = db.Column(db.Float, nullable=True)
    volume_ratio_pct = db.Column(db.Float, nullable=True)

    # Pass/Fail flags for each criteria
    passed_sector_stage = db.Column(db.Boolean, default=False)
    passed_sector_rs = db.Column(db.Boolean, default=False)
    passed_stock_stage = db.Column(db.Boolean, default=False)
    passed_volume = db.Column(db.Boolean, default=False)
    passed_rs = db.Column(db.Boolean, default=False)

    # Timestamps
    added_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    scan_result = db.relationship('AlignedBreakoutScanResult', backref=db.backref('watchlist', lazy='dynamic'))
    instrument = db.relationship('Instrument')

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('scan_result_id', 'instrument_id', name='uq_scan_instrument'),
        db.Index('idx_watchlist_score', 'scan_result_id', 'score_total'),
    )

    def __repr__(self):
        return f'<AlignedBreakoutWatchlist {self.tradingsymbol} Score:{self.score_total:.2f}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'tradingsymbol': self.tradingsymbol,
            'sector_name': self.sector_name,
            'subsector_name': self.subsector_name,
            'score_total': self.score_total,
            'score_sector_alignment': self.score_sector_alignment,
            'score_stock_stage': self.score_stock_stage,
            'score_volume': self.score_volume,
            'score_rs': self.score_rs,
            'current_price': self.current_price,
            'distance_from_52w_high_pct': self.distance_from_52w_high_pct,
            'rs_vs_nifty50': self.rs_vs_nifty50,
            'rs_vs_sector': self.rs_vs_sector,
            'rs_vs_subsector': self.rs_vs_subsector,
            'volume_ratio_pct': self.volume_ratio_pct,
            'passed_sector_stage': self.passed_sector_stage,
            'passed_sector_rs': self.passed_sector_rs,
            'passed_stock_stage': self.passed_stock_stage,
            'passed_volume': self.passed_volume,
            'passed_rs': self.passed_rs
        }


class AlignedBreakoutStageTransition(db.Model):
    """Track when stocks/sectors/subsectors enter each stage"""

    __tablename__ = 'aligned_breakout_stage_transitions'

    id = db.Column(db.Integer, primary_key=True)

    # Entity type and reference
    entity_type = db.Column(db.String(20), nullable=False, index=True)  # 'stock', 'sector', 'subsector'
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=True, index=True)
    sector_id = db.Column(db.Integer, db.ForeignKey('sectors.id'), nullable=True, index=True)
    subsector_id = db.Column(db.Integer, db.ForeignKey('sub_sectors.id'), nullable=True, index=True)

    # Stage transition details
    from_stage = db.Column(db.Integer, nullable=True)  # Previous stage (null if first entry)
    to_stage = db.Column(db.Integer, nullable=False, index=True)  # New stage
    transition_date = db.Column(db.Date, nullable=False, index=True)

    # Confidence and price at transition
    stage_confidence = db.Column(db.Float, nullable=True)
    price_at_transition = db.Column(db.Float, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    instrument = db.relationship('Instrument', foreign_keys=[instrument_id])
    sector = db.relationship('Sector', foreign_keys=[sector_id])
    subsector = db.relationship('SubSector', foreign_keys=[subsector_id])

    # Indexes
    __table_args__ = (
        db.Index('idx_transition_lookup', 'entity_type', 'instrument_id', 'sector_id', 'subsector_id', 'transition_date'),
    )

    def __repr__(self):
        return f'<AlignedBreakoutStageTransition {self.entity_type} Stage:{self.from_stage}->{self.to_stage}>'


class AlignedBreakoutRSHistory(db.Model):
    """Daily RS snapshots for trend detection"""

    __tablename__ = 'aligned_breakout_rs_history'

    id = db.Column(db.Integer, primary_key=True)

    # Entity type and reference
    entity_type = db.Column(db.String(20), nullable=False, index=True)  # 'stock', 'sector', 'subsector'
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=True, index=True)
    sector_id = db.Column(db.Integer, db.ForeignKey('sectors.id'), nullable=True, index=True)
    subsector_id = db.Column(db.Integer, db.ForeignKey('sub_sectors.id'), nullable=True, index=True)

    # RS values
    rs_vs_nifty50 = db.Column(db.Float, nullable=True)
    rs_vs_sector = db.Column(db.Float, nullable=True)  # Only for stocks
    rs_vs_subsector = db.Column(db.Float, nullable=True)  # Only for stocks

    # Date snapshot
    calculated_date = db.Column(db.Date, nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    instrument = db.relationship('Instrument', foreign_keys=[instrument_id])
    sector = db.relationship('Sector', foreign_keys=[sector_id])
    subsector = db.relationship('SubSector', foreign_keys=[subsector_id])

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('entity_type', 'instrument_id', 'sector_id', 'subsector_id', 'calculated_date',
                          name='uq_rs_entity_date'),
        db.Index('idx_rs_lookup', 'entity_type', 'instrument_id', 'sector_id', 'subsector_id', 'calculated_date'),
    )

    def __repr__(self):
        return f'<AlignedBreakoutRSHistory {self.entity_type} Date:{self.calculated_date}>'


class AlignedBreakoutVolumeEvent(db.Model):
    """Track volume breakout events"""

    __tablename__ = 'aligned_breakout_volume_events'

    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=False, index=True)

    # Event details
    event_date = db.Column(db.Date, nullable=False, index=True)
    event_type = db.Column(db.String(20), nullable=False)  # 'breakout', 'accumulation'
    volume = db.Column(db.BigInteger, nullable=True)
    volume_ratio_pct = db.Column(db.Float, nullable=True)  # Volume as % of 50-day avg
    price_at_event = db.Column(db.Float, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    instrument = db.relationship('Instrument')

    # Indexes
    __table_args__ = (
        db.Index('idx_volume_event_lookup', 'instrument_id', 'event_date', 'event_type'),
    )

    def __repr__(self):
        return f'<AlignedBreakoutVolumeEvent {self.instrument_id} Type:{self.event_type} Date:{self.event_date}>'


class AlignedBreakout52WeekTracking(db.Model):
    """Track 52-week high/low changes"""

    __tablename__ = 'aligned_breakout_52week_tracking'

    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=False, index=True)

    # 52-week data
    week_52_high = db.Column(db.Float, nullable=True)
    week_52_low = db.Column(db.Float, nullable=True)
    week_52_high_date = db.Column(db.Date, nullable=True)
    week_52_low_date = db.Column(db.Date, nullable=True)

    # Snapshot date
    snapshot_date = db.Column(db.Date, nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    instrument = db.relationship('Instrument')

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('instrument_id', 'snapshot_date', name='uq_52week_instrument_date'),
        db.Index('idx_52week_lookup', 'instrument_id', 'snapshot_date'),
    )

    def __repr__(self):
        return f'<AlignedBreakout52WeekTracking {self.instrument_id} Date:{self.snapshot_date}>'


class AlignedBreakoutMACalculation(db.Model):
    """Daily MA values and slopes"""

    __tablename__ = 'aligned_breakout_ma_calculations'

    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.id'), nullable=False, index=True)

    # MA values
    ma_150_value = db.Column(db.Float, nullable=True)
    ma_150_slope = db.Column(db.Float, nullable=True)  # Slope (positive = trending up)

    # Snapshot date
    calculated_date = db.Column(db.Date, nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    instrument = db.relationship('Instrument')

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('instrument_id', 'calculated_date', name='uq_ma_instrument_date'),
        db.Index('idx_ma_lookup', 'instrument_id', 'calculated_date'),
    )

    def __repr__(self):
        return f'<AlignedBreakoutMACalculation {self.instrument_id} Date:{self.calculated_date}>'


class AlignedBreakoutScanSnapshot(db.Model):
    """Point-in-time scan result snapshots"""

    __tablename__ = 'aligned_breakout_scan_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    scan_result_id = db.Column(db.Integer, db.ForeignKey('aligned_breakout_scan_results.id'), nullable=False, index=True)

    # Snapshot data (stored as JSON)
    snapshot_data = db.Column(db.Text, nullable=True)  # JSON string with full scan state

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    scan_result = db.relationship('AlignedBreakoutScanResult', backref=db.backref('snapshots', lazy='dynamic'))

    def __repr__(self):
        return f'<AlignedBreakoutScanSnapshot ScanResult:{self.scan_result_id}>'

    def get_snapshot_data(self):
        """Parse and return snapshot data as Python dict"""
        import json
        try:
            return json.loads(self.snapshot_data) if self.snapshot_data else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_snapshot_data(self, data_dict):
        """Set snapshot data from Python dict (converts to JSON)"""
        import json
        self.snapshot_data = json.dumps(data_dict)


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))
