from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import User, Watchlist, WatchlistItem, Instrument
from app import db
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    """Main dashboard page - requires authentication"""

    # Get some statistics for the dashboard
    total_users = User.query.count()

    # Format last login time
    last_login = current_user.last_login.strftime('%B %d, %Y at %I:%M %p') if current_user.last_login else 'First time login'

    # Calculate days since registration
    from datetime import datetime
    days_member = (datetime.utcnow() - current_user.created_at).days

    # Portfolio Statistics
    watchlists_count = current_user.watchlists.count()

    # Total stocks in all watchlists
    total_stocks_tracked = db.session.query(func.count(WatchlistItem.id)).join(Watchlist).filter(
        Watchlist.user_id == current_user.id
    ).scalar() or 0

    # Total instruments in database
    total_instruments = Instrument.query.filter_by(instrument_type='EQ').count()

    # Get recent watchlists (last 3)
    recent_watchlists = current_user.watchlists.order_by(Watchlist.created_at.desc()).limit(3).all()

    # Get watchlist data with item counts
    watchlist_data = []
    for wl in recent_watchlists:
        watchlist_data.append({
            'watchlist': wl,
            'item_count': wl.items.count()
        })

    stats = {
        'total_users': total_users,
        'last_login': last_login,
        'days_member': days_member,
        'account_status': 'Active' if current_user.is_active else 'Inactive',
        'watchlists_count': watchlists_count,
        'total_stocks_tracked': total_stocks_tracked,
        'total_instruments': total_instruments
    }

    return render_template('dashboard/index.html',
                         title='Dashboard',
                         stats=stats,
                         recent_watchlists=watchlist_data)


@dashboard_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('dashboard/profile.html', title='Profile')
