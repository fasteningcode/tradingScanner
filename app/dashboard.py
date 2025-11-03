from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import User
from app import db

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

    stats = {
        'total_users': total_users,
        'last_login': last_login,
        'days_member': days_member,
        'account_status': 'Active' if current_user.is_active else 'Inactive'
    }

    return render_template('dashboard/index.html', title='Dashboard', stats=stats)


@dashboard_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('dashboard/profile.html', title='Profile')
