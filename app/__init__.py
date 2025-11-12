from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from config import config
import logging
from logging.handlers import RotatingFileHandler
import os

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()


def create_app(config_name='default'):
    """
    Application factory pattern for creating Flask app instances

    Args:
        config_name: Configuration name ('development', 'production', 'testing', or 'default')

    Returns:
        Flask application instance
    """
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(config[config_name])

    # Setup logging
    setup_logging(app)

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Configure Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # Register blueprints
    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.settings import settings_bp
    from app.kite_auth import kite_bp
    from app.stocks import stocks_bp
    from app.watchlist import watchlist_bp
    from app.scanner_routes import scanner_bp
    from app.sectors import sectors_bp
    from app.sector_management import sector_management_bp
    from app.orders import orders_bp
    from app.positions import positions_bp
    from app.backtest import backtest_bp
    from app.routes.aligned_breakout_api import aligned_breakout_api
    from app.api_routes import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(kite_bp)
    app.register_blueprint(stocks_bp)
    app.register_blueprint(watchlist_bp)
    app.register_blueprint(scanner_bp)
    app.register_blueprint(sectors_bp)
    app.register_blueprint(sector_management_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(positions_bp)
    app.register_blueprint(backtest_bp)
    app.register_blueprint(aligned_breakout_api)

    # Create database tables
    with app.app_context():
        db.create_all()

        # Enable WAL mode for SQLite to prevent database locks
        # WAL (Write-Ahead Logging) allows concurrent reads and writes
        if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.execute(text("PRAGMA synchronous=NORMAL"))
                conn.execute(text("PRAGMA busy_timeout=30000"))  # 30 seconds
                conn.commit()
                app.logger.info("SQLite WAL mode enabled for concurrent access")

    # Add cache control headers to prevent stale data
    @app.after_request
    def add_header(response):
        """Add headers to prevent caching of dynamic pages"""
        # Don't cache HTML pages
        if response.content_type and 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '-1'
        return response

    # Register error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        db.session.rollback()
        return render_template('500.html'), 500

    return app


def setup_logging(app):
    """Configure application logging to file and console"""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.mkdir('logs')

    # File handler for general logs
    file_handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    # File handler for errors only
    error_handler = RotatingFileHandler(
        'logs/error.log',
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    error_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    error_handler.setLevel(logging.ERROR)
    app.logger.addHandler(error_handler)

    # File handler for access logs
    access_handler = RotatingFileHandler(
        'logs/access.log',
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    access_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(message)s'
    ))
    access_handler.setLevel(logging.INFO)

    # Add access log handler to werkzeug
    logging.getLogger('werkzeug').addHandler(access_handler)
    logging.getLogger('werkzeug').setLevel(logging.INFO)

    app.logger.setLevel(logging.INFO)
    app.logger.info('Flask application startup')
