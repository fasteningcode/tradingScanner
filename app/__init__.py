from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from config import config

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

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(kite_bp)
    app.register_blueprint(stocks_bp)
    app.register_blueprint(watchlist_bp)
    app.register_blueprint(scanner_bp)
    app.register_blueprint(sectors_bp)
    app.register_blueprint(sector_management_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(positions_bp)
    app.register_blueprint(backtest_bp)

    # Create database tables
    with app.app_context():
        db.create_all()

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
