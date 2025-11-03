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


class Instrument(db.Model):
    """Model for storing instrument/stock data with custom sector mapping"""

    __tablename__ = 'instruments'

    id = db.Column(db.Integer, primary_key=True)
    instrument_token = db.Column(db.Integer, unique=True, nullable=False, index=True)
    exchange_token = db.Column(db.Integer, nullable=True)
    tradingsymbol = db.Column(db.String(50), nullable=False, index=True)
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
    sector = db.Column(db.String(100), nullable=True, index=True)
    sub_sector = db.Column(db.String(100), nullable=True, index=True)
    custom_tags = db.Column(db.Text, nullable=True)  # JSON string for custom tags

    # Timestamps
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
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


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))
