import os
from datetime import datetime, timedelta
from flask import Blueprint, redirect, url_for, flash, request, session, current_app
from flask_login import login_required, current_user
from kiteconnect import KiteConnect
from app import db

kite_bp = Blueprint('kite', __name__, url_prefix='/kite')


def get_kite_client(access_token=None):
    """
    Get initialized Kite Connect client

    Args:
        access_token: Optional access token. If not provided, will use current_user's token

    Returns:
        KiteConnect instance
    """
    api_key = os.environ.get('KITE_API_KEY')
    if not api_key:
        raise ValueError('KITE_API_KEY not configured in environment')

    kite = KiteConnect(api_key=api_key)

    if access_token:
        kite.set_access_token(access_token)
    elif current_user.is_authenticated and current_user.kite_access_token:
        kite.set_access_token(current_user.kite_access_token)

    return kite


@kite_bp.route('/connect')
@login_required
def connect():
    """
    Initiate Kite Connect authentication flow
    Redirects user to Zerodha login page
    """
    try:
        api_key = os.environ.get('KITE_API_KEY')
        if not api_key:
            flash('Kite Connect API credentials not configured. Please contact administrator.', 'danger')
            return redirect(url_for('dashboard.index'))

        kite = KiteConnect(api_key=api_key)
        login_url = kite.login_url()

        # Store state in session for verification in callback
        session['kite_connect_initiated'] = datetime.utcnow().isoformat()

        current_app.logger.info(f'User {current_user.username} initiating Kite Connect')
        return redirect(login_url)

    except Exception as e:
        current_app.logger.error(f'Error initiating Kite Connect: {str(e)}')
        flash(f'Error connecting to Kite: {str(e)}', 'danger')
        return redirect(url_for('dashboard.index'))


@kite_bp.route('/callback')
@login_required
def callback():
    """
    Handle Kite Connect callback after user authorizes the app
    Exchange request_token for access_token
    """
    try:
        # Verify session state
        if 'kite_connect_initiated' not in session:
            flash('Invalid Kite Connect callback. Please try again.', 'danger')
            return redirect(url_for('dashboard.index'))

        # Get request token from query parameters
        request_token = request.args.get('request_token')
        status = request.args.get('status')

        if not request_token or status != 'success':
            flash('Kite Connect authorization failed or was cancelled.', 'warning')
            return redirect(url_for('dashboard.index'))

        # Get API credentials
        api_key = os.environ.get('KITE_API_KEY')
        api_secret = os.environ.get('KITE_API_SECRET')

        if not api_key or not api_secret:
            flash('Kite Connect API credentials not configured properly.', 'danger')
            return redirect(url_for('dashboard.index'))

        # Initialize Kite Connect client
        kite = KiteConnect(api_key=api_key)

        # Generate session (exchange request_token for access_token)
        data = kite.generate_session(request_token, api_secret=api_secret)

        # Extract credentials
        access_token = data.get('access_token')
        user_id = data.get('user_id')
        public_token = data.get('public_token')
        refresh_token = data.get('refresh_token')

        # Calculate token expiry (Kite tokens expire at 7:30 AM next day)
        # Set to 7:30 AM of next day IST
        now = datetime.utcnow()
        # Kite tokens expire at 7:30 AM IST (2:00 AM UTC)
        next_day = now + timedelta(days=1)
        token_expiry = datetime(next_day.year, next_day.month, next_day.day, 2, 0, 0)

        # If current time is past 2:00 AM UTC, token expires at 2:00 AM UTC today
        if now.hour < 2:
            token_expiry = datetime(now.year, now.month, now.day, 2, 0, 0)

        # Update user's Kite credentials
        current_user.update_kite_credentials(
            access_token=access_token,
            user_id=user_id,
            public_token=public_token,
            refresh_token=refresh_token,
            expires_at=token_expiry
        )

        # Clear session state
        session.pop('kite_connect_initiated', None)

        current_app.logger.info(f'User {current_user.username} successfully connected to Kite (User ID: {user_id})')
        flash(f'Successfully connected to Kite! Your Zerodha User ID: {user_id}', 'success')

        return redirect(url_for('dashboard.index'))

    except Exception as e:
        current_app.logger.error(f'Error in Kite Connect callback: {str(e)}')
        flash(f'Error completing Kite Connect authorization: {str(e)}', 'danger')
        return redirect(url_for('dashboard.index'))


@kite_bp.route('/disconnect', methods=['POST'])
@login_required
def disconnect():
    """
    Disconnect Kite Connect account
    """
    try:
        # Clear Kite credentials
        current_user.kite_access_token = None
        current_user.kite_user_id = None
        current_user.kite_public_token = None
        current_user.kite_refresh_token = None
        current_user.kite_access_token_expires = None
        current_user.kite_connected = False
        current_user.kite_last_connected = None
        db.session.commit()

        current_app.logger.info(f'User {current_user.username} disconnected from Kite')
        flash('Kite Connect account disconnected successfully.', 'success')

    except Exception as e:
        current_app.logger.error(f'Error disconnecting Kite: {str(e)}')
        flash(f'Error disconnecting Kite account: {str(e)}', 'danger')

    return redirect(url_for('dashboard.index'))


@kite_bp.route('/status')
@login_required
def status():
    """
    Check Kite Connect connection status and token validity
    """
    try:
        if not current_user.kite_connected or not current_user.kite_access_token:
            return {
                'connected': False,
                'message': 'Not connected to Kite'
            }, 200

        # Check token validity
        token_valid = current_user.is_kite_token_valid()

        if not token_valid:
            return {
                'connected': True,
                'token_valid': False,
                'message': 'Access token expired. Please reconnect.',
                'kite_user_id': current_user.kite_user_id,
                'expires_at': current_user.kite_access_token_expires.isoformat() if current_user.kite_access_token_expires else None
            }, 200

        # Test connection by fetching profile
        kite = get_kite_client()
        profile = kite.profile()

        return {
            'connected': True,
            'token_valid': True,
            'kite_user_id': current_user.kite_user_id,
            'user_name': profile.get('user_name'),
            'email': profile.get('email'),
            'broker': profile.get('broker'),
            'expires_at': current_user.kite_access_token_expires.isoformat() if current_user.kite_access_token_expires else None,
            'last_connected': current_user.kite_last_connected.isoformat() if current_user.kite_last_connected else None
        }, 200

    except Exception as e:
        current_app.logger.error(f'Error checking Kite status: {str(e)}')
        return {
            'connected': True,
            'token_valid': False,
            'error': str(e),
            'message': 'Error validating connection. Please reconnect.'
        }, 200
