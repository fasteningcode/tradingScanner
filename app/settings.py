import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app, session, jsonify
from flask_login import login_required, current_user, logout_user
from werkzeug.utils import secure_filename
from app import db
from app.models import User, HistoricalDataSettings, HistoricalData, DownloadTask, DownloadLog, Instrument, StockInformation, MarketCapFetchTask
from app.forms import BackupForm, RestoreDatabaseForm, EmergencyRestoreForm, KiteCredentialsForm
from app.kite_auth import get_kite_client
from app import marketcap_service

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

# Simple in-memory rate limiting for emergency restore
emergency_restore_attempts = {}


@settings_bp.route('/')
@settings_bp.route('/<tab>')
@login_required
def index(tab='general'):
    """Settings page with tabbed interface"""
    valid_tabs = ['general', 'backup', 'security', 'kite', 'historical', 'about']
    if tab not in valid_tabs:
        tab = 'general'

    # Get app info for About tab
    app_info = {
        'version': '1.0.0',
        'flask_version': current_app.config.get('FLASK_VERSION', 'Unknown'),
        'database': 'SQLite',
        'users_count': User.query.count()
    }

    backup_form = BackupForm()
    restore_form = RestoreDatabaseForm()
    kite_form = KiteCredentialsForm()

    # Pre-populate Kite form with current values
    if current_user.kite_access_token:
        kite_form.access_token.data = current_user.kite_access_token
        kite_form.user_id.data = current_user.kite_user_id or ''
        kite_form.public_token.data = current_user.kite_public_token or ''
        kite_form.refresh_token.data = current_user.kite_refresh_token or ''

    # Get historical data settings for current user
    historical_settings = HistoricalDataSettings.query.filter_by(user_id=current_user.id).first()

    return render_template('settings/index.html',
                         title='Settings',
                         active_tab=tab,
                         app_info=app_info,
                         backup_form=backup_form,
                         restore_form=restore_form,
                         kite_form=kite_form,
                         historical_settings=historical_settings)


@settings_bp.route('/backup', methods=['POST'])
@login_required
def backup_database():
    """Create and download database backup"""
    try:
        # Get the database file path
        db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
            # For relative paths, SQLite uses Flask's instance folder
            if not os.path.isabs(db_path):
                db_full_path = os.path.join(current_app.instance_path, db_path)
            else:
                db_full_path = db_path
        else:
            flash('Backup only supported for SQLite databases.', 'danger')
            return redirect(url_for('settings.index', tab='backup'))

        if not os.path.exists(db_full_path):
            flash(f'Database file not found at: {db_full_path}', 'danger')
            return redirect(url_for('settings.index', tab='backup'))

        # Create backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'backup_{timestamp}.db'

        # Create a temporary backup file
        temp_backup_path = os.path.join(current_app.root_path, 'static', backup_filename)

        # Copy the database file
        shutil.copy2(db_full_path, temp_backup_path)

        # Send file to user
        response = send_file(
            temp_backup_path,
            as_attachment=True,
            download_name=backup_filename,
            mimetype='application/x-sqlite3'
        )

        # Clean up temp file after sending (using after_request would be better in production)
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(temp_backup_path):
                    os.remove(temp_backup_path)
            except Exception:
                pass

        flash(f'Database backup created successfully: {backup_filename}', 'success')
        return response

    except Exception as e:
        flash(f'Error creating backup: {str(e)}', 'danger')
        return redirect(url_for('settings.index', tab='backup'))


@settings_bp.route('/restore', methods=['POST'])
@login_required
def restore_database():
    """Restore database from uploaded file"""
    form = RestoreDatabaseForm()

    if form.validate_on_submit():
        # Verify password
        if not current_user.check_password(form.password.data):
            flash('Incorrect password. Database restore cancelled.', 'danger')
            return redirect(url_for('settings.index', tab='backup'))

        uploaded_file = form.database_file.data

        if not uploaded_file:
            flash('No file uploaded.', 'danger')
            return redirect(url_for('settings.index', tab='backup'))

        try:
            # Get database path
            db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
            if db_uri.startswith('sqlite:///'):
                db_path = db_uri.replace('sqlite:///', '')
                # For relative paths, SQLite uses Flask's instance folder
                if not os.path.isabs(db_path):
                    db_full_path = os.path.join(current_app.instance_path, db_path)
                else:
                    db_full_path = db_path
            else:
                flash('Restore only supported for SQLite databases.', 'danger')
                return redirect(url_for('settings.index', tab='backup'))

            # Create backup of current database before restore
            if os.path.exists(db_full_path):
                backup_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                auto_backup_path = db_full_path + f'.backup_{backup_timestamp}'
                shutil.copy2(db_full_path, auto_backup_path)

            # Save uploaded file temporarily
            temp_upload_path = os.path.join(current_app.root_path, 'static', 'temp_restore.db')
            uploaded_file.save(temp_upload_path)

            # Validate it's a SQLite database
            try:
                conn = sqlite3.connect(temp_upload_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                conn.close()

                # Check if it has the users table (basic validation)
                if not any('users' in str(table).lower() for table in tables):
                    os.remove(temp_upload_path)
                    flash('Invalid database file: users table not found.', 'danger')
                    return redirect(url_for('settings.index', tab='backup'))

            except sqlite3.Error as e:
                if os.path.exists(temp_upload_path):
                    os.remove(temp_upload_path)
                flash(f'Invalid database file: {str(e)}', 'danger')
                return redirect(url_for('settings.index', tab='backup'))

            # Close all database connections
            db.session.remove()
            db.engine.dispose()

            # Replace the current database with uploaded one
            shutil.move(temp_upload_path, db_full_path)

            # Reinitialize database connection
            db.engine.dispose()

            flash('Database restored successfully! Please log in again.', 'success')

            # Logout user for security
            from flask_login import logout_user
            logout_user()

            return redirect(url_for('auth.login'))

        except Exception as e:
            flash(f'Error restoring database: {str(e)}', 'danger')
            # Clean up temp file if it exists
            temp_file = os.path.join(current_app.root_path, 'static', 'temp_restore.db')
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return redirect(url_for('settings.index', tab='backup'))

    # If form validation fails
    flash('Please fill in all required fields.', 'danger')
    return redirect(url_for('settings.index', tab='backup'))


@settings_bp.route('/emergency-restore', methods=['GET', 'POST'])
def emergency_restore():
    """Emergency database restore with emergency password (no login required)"""
    form = EmergencyRestoreForm()

    if request.method == 'POST':
        # Rate limiting check
        client_ip = request.remote_addr
        now = datetime.now()

        # Clean old attempts (older than 1 hour)
        emergency_restore_attempts.update({
            ip: attempts for ip, attempts in emergency_restore_attempts.items()
            if attempts[-1] > now - timedelta(hours=1)
        })

        # Check rate limit (max 5 attempts per hour per IP)
        if client_ip in emergency_restore_attempts:
            attempts = [t for t in emergency_restore_attempts[client_ip] if t > now - timedelta(hours=1)]
            if len(attempts) >= 5:
                flash('Too many emergency restore attempts. Please try again later.', 'danger')
                return render_template('settings/emergency_restore.html', form=form)
            emergency_restore_attempts[client_ip] = attempts + [now]
        else:
            emergency_restore_attempts[client_ip] = [now]

        if form.validate_on_submit():
            # Verify emergency password
            emergency_password = os.environ.get('EMERGENCY_RESTORE_PASSWORD')
            if not emergency_password or form.emergency_password.data != emergency_password:
                flash('Invalid emergency restore password.', 'danger')
                current_app.logger.warning(f'Failed emergency restore attempt from IP: {client_ip}')
                return render_template('settings/emergency_restore.html', form=form)

            uploaded_file = form.database_file.data

            if not uploaded_file:
                flash('No file uploaded.', 'danger')
                return render_template('settings/emergency_restore.html', form=form)

            try:
                # Get database path
                db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
                if db_uri.startswith('sqlite:///'):
                    db_path = db_uri.replace('sqlite:///', '')
                    # For relative paths, SQLite uses Flask's instance folder
                    if not os.path.isabs(db_path):
                        db_full_path = os.path.join(current_app.instance_path, db_path)
                    else:
                        db_full_path = db_path
                else:
                    flash('Emergency restore only supported for SQLite databases.', 'danger')
                    return render_template('settings/emergency_restore.html', form=form)

                # Create automatic backup of current database before restore
                if os.path.exists(db_full_path):
                    backup_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    auto_backup_path = db_full_path + f'.emergency_backup_{backup_timestamp}'
                    shutil.copy2(db_full_path, auto_backup_path)
                    current_app.logger.info(f'Emergency restore: Created automatic backup at {auto_backup_path}')

                # Save uploaded file temporarily
                temp_upload_path = os.path.join(current_app.root_path, 'static', 'temp_emergency_restore.db')
                uploaded_file.save(temp_upload_path)

                # Validate it's a SQLite database
                try:
                    conn = sqlite3.connect(temp_upload_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = cursor.fetchall()
                    conn.close()

                    # Check if it has the users table (basic validation)
                    if not any('users' in str(table).lower() for table in tables):
                        os.remove(temp_upload_path)
                        flash('Invalid database file: users table not found.', 'danger')
                        return render_template('settings/emergency_restore.html', form=form)

                except sqlite3.Error as e:
                    if os.path.exists(temp_upload_path):
                        os.remove(temp_upload_path)
                    flash(f'Invalid database file: {str(e)}', 'danger')
                    return render_template('settings/emergency_restore.html', form=form)

                # Close all database connections
                db.session.remove()
                db.engine.dispose()

                # Replace the current database with uploaded one
                shutil.move(temp_upload_path, db_full_path)

                # Reinitialize database connection
                db.engine.dispose()

                current_app.logger.info(f'Emergency restore successful from IP: {client_ip}')
                flash('Emergency database restore successful! Please log in.', 'success')

                # Logout any logged-in user for security
                if current_user.is_authenticated:
                    logout_user()

                return redirect(url_for('auth.login'))

            except Exception as e:
                current_app.logger.error(f'Emergency restore error: {str(e)}')
                flash(f'Error during emergency restore: {str(e)}', 'danger')
                # Clean up temp file if it exists
                temp_file = os.path.join(current_app.root_path, 'static', 'temp_emergency_restore.db')
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                return render_template('settings/emergency_restore.html', form=form)

        # If form validation fails
        flash('Please fill in all required fields correctly.', 'danger')

    return render_template('settings/emergency_restore.html', form=form)


@settings_bp.route('/kite/update-credentials', methods=['POST'])
@login_required
def update_kite_credentials():
    """Manually update Kite Connect credentials"""
    form = KiteCredentialsForm()

    if form.validate_on_submit():
        try:
            # Calculate token expiry (7:30 AM IST = 2:00 AM UTC)
            now = datetime.utcnow()
            next_day = now + timedelta(days=1)
            token_expiry = datetime(next_day.year, next_day.month, next_day.day, 2, 0, 0)
            if now.hour < 2:
                token_expiry = datetime(now.year, now.month, now.day, 2, 0, 0)

            # Update user credentials
            current_user.update_kite_credentials(
                access_token=form.access_token.data,
                user_id=form.user_id.data,
                public_token=form.public_token.data if form.public_token.data else None,
                refresh_token=form.refresh_token.data if form.refresh_token.data else None,
                expires_at=token_expiry
            )

            flash('Kite Connect credentials updated successfully!', 'success')
            current_app.logger.info(f'User {current_user.username} manually updated Kite credentials')

        except Exception as e:
            flash(f'Error updating Kite credentials: {str(e)}', 'danger')
            current_app.logger.error(f'Error updating Kite credentials: {str(e)}')

        return redirect(url_for('settings.index', tab='kite'))

    # If form validation fails
    flash('Please fill in all required fields correctly.', 'danger')
    return redirect(url_for('settings.index', tab='kite'))


@settings_bp.route('/kite/validate-token', methods=['POST'])
@login_required
def validate_kite_token():
    """Validate Kite access token by fetching user profile"""
    try:
        if not current_user.kite_access_token:
            return jsonify({
                'valid': False,
                'error': 'No access token found. Please connect to Kite first.'
            })

        # Try to fetch profile using current access token
        kite = get_kite_client(access_token=current_user.kite_access_token)
        profile = kite.profile()

        # If successful, token is valid
        return jsonify({
            'valid': True,
            'profile': {
                'user_id': profile.get('user_id'),
                'user_name': profile.get('user_name'),
                'user_shortname': profile.get('user_shortname'),
                'email': profile.get('email'),
                'broker': profile.get('broker'),
                'products': profile.get('products', []),
                'exchanges': profile.get('exchanges', [])
            },
            'expires_at': current_user.kite_access_token_expires.strftime('%B %d, %Y at %I:%M %p UTC') if current_user.kite_access_token_expires else 'Unknown'
        })

    except Exception as e:
        error_message = str(e)
        current_app.logger.error(f'Kite token validation failed: {error_message}')

        # Token is invalid or expired
        return jsonify({
            'valid': False,
            'error': error_message
        })


@settings_bp.route('/kite/clear-credentials', methods=['POST'])
@login_required
def clear_kite_credentials():
    """Clear Kite Connect credentials"""
    try:
        current_user.kite_access_token = None
        current_user.kite_access_token_expires = None
        current_user.kite_user_id = None
        current_user.kite_public_token = None
        current_user.kite_refresh_token = None
        current_user.kite_connected = False
        current_user.kite_last_connected = None
        db.session.commit()

        flash('Kite Connect credentials cleared successfully.', 'success')
        current_app.logger.info(f'User {current_user.username} cleared Kite credentials')

    except Exception as e:
        flash(f'Error clearing Kite credentials: {str(e)}', 'danger')
        current_app.logger.error(f'Error clearing Kite credentials: {str(e)}')

    return redirect(url_for('settings.index', tab='kite'))


@settings_bp.route('/historical-data/update', methods=['POST'])
@login_required
def update_historical_data_settings():
    """Update historical data settings for the current user"""
    try:
        # Get or create historical data settings for the user
        settings = HistoricalDataSettings.query.filter_by(user_id=current_user.id).first()
        if not settings:
            settings = HistoricalDataSettings(user_id=current_user.id)
            db.session.add(settings)

        # Update settings from form data
        settings.requests_per_second = int(request.form.get('requests_per_second', 1))
        settings.candle_interval = request.form.get('candle_interval', 'day')
        settings.date_preset = request.form.get('date_preset', '1month')

        # Handle custom date range if selected
        if settings.date_preset == 'custom':
            from_date_str = request.form.get('from_date')
            to_date_str = request.form.get('to_date')

            if from_date_str and to_date_str:
                settings.from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                settings.to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            else:
                flash('Please provide both From Date and To Date when using custom range.', 'warning')
                return redirect(url_for('settings.index', tab='historical'))
        else:
            # Clear custom dates if not using custom preset
            settings.from_date = None
            settings.to_date = None

        # Update checkboxes
        settings.continuous_download = request.form.get('continuous_download') == 'on'
        settings.auto_download_new_stocks = request.form.get('auto_download_new_stocks') == 'on'

        # Update timestamp
        settings.updated_at = datetime.utcnow()

        db.session.commit()

        flash('Historical data settings updated successfully!', 'success')
        current_app.logger.info(f'User {current_user.username} updated historical data settings')

    except Exception as e:
        db.session.rollback()
        flash(f'Error updating historical data settings: {str(e)}', 'danger')
        current_app.logger.error(f'Error updating historical data settings: {str(e)}')

    return redirect(url_for('settings.index', tab='historical'))


@settings_bp.route('/historical-data/clear', methods=['GET', 'POST'])
@login_required
def clear_historical_data():
    """Clear all historical data from the database"""
    if request.method == 'GET':
        # Show confirmation page for direct URL access
        data_count = HistoricalData.query.count()
        return render_template('settings/confirm_clear.html', data_count=data_count)

    # POST request - actually clear the data
    try:
        # Delete all historical candle data
        deleted_count = HistoricalData.query.delete()
        db.session.commit()

        flash(f'Successfully cleared {deleted_count} historical data records.', 'success')
        current_app.logger.info(f'User {current_user.username} cleared {deleted_count} historical data records')

    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing historical data: {str(e)}', 'danger')
        current_app.logger.error(f'Error clearing historical data: {str(e)}')

    return redirect(url_for('settings.index', tab='historical'))


@settings_bp.route('/historical-data/start-download', methods=['POST'])
@login_required
def start_download():
    """Start a new historical data download task"""
    # LOG: Request received
    current_app.logger.info("=" * 80)
    current_app.logger.info("START DOWNLOAD REQUEST RECEIVED")
    current_app.logger.info(f"Request method: {request.method}")
    current_app.logger.info(f"Request endpoint: /historical-data/start-download")
    current_app.logger.info(f"User: {current_user.username} (ID: {current_user.id})")
    current_app.logger.info(f"Database URI: {current_app.config.get('SQLALCHEMY_DATABASE_URI')}")
    current_app.logger.info("=" * 80)

    try:
        from app.download_service import create_download_task, get_active_task, HistoricalDataDownloader
        from app.kite_auth import get_kite_client

        current_app.logger.info("Successfully imported download_service and kite_auth modules")

        # PRE-FLIGHT VALIDATION #1: Check Kite connection
        current_app.logger.info("PRE-FLIGHT CHECK #1: Checking Kite connection...")
        current_app.logger.info(f"  - current_user.kite_connected: {current_user.kite_connected}")
        current_app.logger.info(f"  - current_user.kite_access_token exists: {bool(current_user.kite_access_token)}")
        if current_user.kite_access_token:
            current_app.logger.info(f"  - Token length: {len(current_user.kite_access_token)} characters")
            current_app.logger.info(f"  - Token preview: {current_user.kite_access_token[:10]}...{current_user.kite_access_token[-10:]}")

        if not current_user.kite_connected or not current_user.kite_access_token:
            current_app.logger.warning("PRE-FLIGHT CHECK #1: FAILED - No Kite connection or token")
            flash('Please connect to Zerodha Kite first before downloading historical data.', 'warning')
            current_app.logger.info("Redirecting to: settings.index?tab=kite")
            return redirect(url_for('settings.index', tab='kite'))

        current_app.logger.info("PRE-FLIGHT CHECK #1: PASSED - Kite connection exists")

        # PRE-FLIGHT VALIDATION #2: Verify Kite token is valid
        current_app.logger.info("PRE-FLIGHT CHECK #2: Verifying Kite token validity...")
        try:
            token_valid = current_user.is_kite_token_valid()
            current_app.logger.info(f"  - Token valid result: {token_valid}")
        except Exception as e:
            current_app.logger.error(f"  - Error checking token validity: {str(e)}", exc_info=True)
            token_valid = False

        if not token_valid:
            current_app.logger.warning("PRE-FLIGHT CHECK #2: FAILED - Kite token expired or invalid")
            flash('Your Kite access token has expired. Please reconnect to Kite.', 'warning')
            current_app.logger.info("Redirecting to: settings.index?tab=kite")
            return redirect(url_for('settings.index', tab='kite'))

        current_app.logger.info("PRE-FLIGHT CHECK #2: PASSED - Kite token is valid")

        # PRE-FLIGHT VALIDATION #3: Check if there's already an active task
        current_app.logger.info("PRE-FLIGHT CHECK #3: Checking for active download tasks...")
        current_app.logger.info(f"  - Querying active tasks for user_id: {current_user.id}")

        try:
            active_task = get_active_task(current_user.id)
            if active_task:
                current_app.logger.warning(f"PRE-FLIGHT CHECK #3: FAILED - Active task found: Task ID={active_task.id}, Status={active_task.status}")
                current_app.logger.info(f"  - Task details: created_at={active_task.created_at}, started_at={active_task.started_at}")
                current_app.logger.info(f"  - Task progress: {active_task.completed_stocks}/{active_task.total_stocks} completed, {active_task.failed_stocks} failed, {active_task.skipped_stocks} skipped")
                current_app.logger.info(f"  - Progress percentage: {active_task.progress_percentage}%")
                flash(f'You already have an active download task (Status: {active_task.status}). Use Force Reset if stuck.', 'warning')
                current_app.logger.info("Redirecting to: settings.index?tab=historical")
                return redirect(url_for('settings.index', tab='historical'))
            else:
                current_app.logger.info("PRE-FLIGHT CHECK #3: PASSED - No active tasks found")
        except Exception as e:
            current_app.logger.error(f"PRE-FLIGHT CHECK #3: ERROR - Exception while checking active tasks: {str(e)}", exc_info=True)
            flash(f'Error checking active tasks: {str(e)}', 'danger')
            return redirect(url_for('settings.index', tab='historical'))

        # PRE-FLIGHT VALIDATION #4: Verify Kite client can be initialized
        current_app.logger.info("PRE-FLIGHT CHECK #4: Initializing Kite client...")
        try:
            kite_client = get_kite_client(access_token=current_user.kite_access_token)
            current_app.logger.info(f"PRE-FLIGHT CHECK #4: PASSED - Kite client initialized successfully for user {current_user.username}")
            current_app.logger.info(f"  - Kite client type: {type(kite_client)}")
        except Exception as e:
            current_app.logger.error(f"PRE-FLIGHT CHECK #4: FAILED - Kite client initialization error: {str(e)}", exc_info=True)
            flash(f'Failed to initialize Kite client: {str(e)}. Please reconnect to Kite.', 'danger')
            current_app.logger.info("Redirecting to: settings.index?tab=kite")
            return redirect(url_for('settings.index', tab='kite'))

        # PRE-FLIGHT VALIDATION #5: Check that NIFTY 500 stocks exist
        current_app.logger.info("PRE-FLIGHT CHECK #5: Checking NIFTY 500 stocks in database...")
        try:
            from app.models import Instrument
            nifty500_count = Instrument.query.filter_by(is_nifty500=True).count()
            current_app.logger.info(f"  - NIFTY 500 stock count: {nifty500_count}")

            if nifty500_count == 0:
                current_app.logger.warning("PRE-FLIGHT CHECK #5: FAILED - No NIFTY 500 stocks found in database")
                flash('No NIFTY 500 stocks found in database. Please sync instruments first.', 'warning')
                current_app.logger.info("Redirecting to: settings.index?tab=historical")
                return redirect(url_for('settings.index', tab='historical'))

            current_app.logger.info(f"PRE-FLIGHT CHECK #5: PASSED - Found {nifty500_count} NIFTY 500 stocks")
        except Exception as e:
            current_app.logger.error(f"PRE-FLIGHT CHECK #5: ERROR - Exception while counting stocks: {str(e)}", exc_info=True)
            flash(f'Error checking stock database: {str(e)}', 'danger')
            return redirect(url_for('settings.index', tab='historical'))

        # Create new task
        current_app.logger.info("=" * 80)
        current_app.logger.info("ALL PRE-FLIGHT CHECKS PASSED - Creating download task...")
        current_app.logger.info("=" * 80)

        try:
            current_app.logger.info(f"Calling create_download_task(user_id={current_user.id})...")
            task = create_download_task(current_user.id)

            if not task:
                current_app.logger.error("TASK CREATION FAILED - create_download_task returned None")
                current_app.logger.info("Possible reason: No historical data settings configured")
                flash('Please configure historical data settings first.', 'warning')
                current_app.logger.info("Redirecting to: settings.index?tab=historical")
                return redirect(url_for('settings.index', tab='historical'))

            current_app.logger.info(f"TASK CREATION SUCCESS - Created download task ID={task.id}")
            current_app.logger.info(f"  - Task details: status={task.status}, user_id={task.user_id}")
            current_app.logger.info(f"  - Task created_at: {task.created_at}")

        except Exception as e:
            current_app.logger.error(f"TASK CREATION ERROR - Exception during create_download_task: {str(e)}", exc_info=True)
            flash(f'Error creating download task: {str(e)}', 'danger')
            return redirect(url_for('settings.index', tab='historical'))

        # Start download in background
        current_app.logger.info("=" * 80)
        current_app.logger.info(f"STARTING DOWNLOAD - Initializing HistoricalDataDownloader for task {task.id}...")
        current_app.logger.info("=" * 80)

        try:
            current_app.logger.info(f"Creating HistoricalDataDownloader(task_id={task.id})...")
            downloader = HistoricalDataDownloader(task.id)
            current_app.logger.info(f"  - Downloader instance created: {type(downloader)}")

            current_app.logger.info(f"Calling downloader.start_download()...")
            downloader.start_download()
            current_app.logger.info("  - start_download() call completed")

            # Check if task status was updated
            db.session.expire(task)
            updated_task = DownloadTask.query.get(task.id)
            current_app.logger.info(f"  - Task status after start_download: {updated_task.status}")
            current_app.logger.info(f"  - Task total_stocks: {updated_task.total_stocks}")
            current_app.logger.info(f"  - Task completed_stocks: {updated_task.completed_stocks}")
            current_app.logger.info(f"  - Task progress: {updated_task.progress_percentage}%")

        except Exception as e:
            current_app.logger.error(f"DOWNLOAD START ERROR - Exception during downloader initialization or start: {str(e)}", exc_info=True)
            flash(f'Error starting download: {str(e)}', 'danger')
            return redirect(url_for('settings.index', tab='historical'))

        flash('Historical data download started in background! Check the progress below.', 'success')
        current_app.logger.info("=" * 80)
        current_app.logger.info(f"DOWNLOAD STARTED SUCCESSFULLY - Task {task.id} is now running")
        current_app.logger.info(f"User {current_user.username} successfully started download task {task.id}")
        current_app.logger.info("Redirecting to: settings.index?tab=historical")
        current_app.logger.info("=" * 80)

    except Exception as e:
        current_app.logger.error("=" * 80)
        current_app.logger.error("UNEXPECTED ERROR IN START_DOWNLOAD ENDPOINT")
        current_app.logger.error(f"Error type: {type(e).__name__}")
        current_app.logger.error(f"Error message: {str(e)}")
        current_app.logger.error("Full traceback:", exc_info=True)
        current_app.logger.error("=" * 80)
        flash(f'Error starting download: {str(e)}', 'danger')

    return redirect(url_for('settings.index', tab='historical'))


@settings_bp.route('/historical-data/pause-download/<int:task_id>', methods=['POST'])
@login_required
def pause_download(task_id):
    """Pause a running download task"""
    try:
        from app.download_service import active_downloads

        # Verify task belongs to user
        task = DownloadTask.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

        if task.status != 'running':
            flash(f'Task is not running (Status: {task.status}).', 'warning')
            return redirect(url_for('settings.index', tab='historical'))

        # Pause the download
        if task_id in active_downloads:
            downloader = active_downloads[task_id]
            downloader.pause_download()
            flash('Download paused successfully.', 'success')
        else:
            flash('Download task not found in active downloads.', 'warning')

        current_app.logger.info(f'User {current_user.username} paused download task {task_id}')

    except Exception as e:
        flash(f'Error pausing download: {str(e)}', 'danger')
        current_app.logger.error(f'Error pausing download: {str(e)}')

    return redirect(url_for('settings.index', tab='historical'))


@settings_bp.route('/historical-data/resume-download/<int:task_id>', methods=['POST'])
@login_required
def resume_download(task_id):
    """Resume a paused download task"""
    try:
        from app.download_service import HistoricalDataDownloader

        # Verify task belongs to user
        task = DownloadTask.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

        if task.status != 'paused':
            flash(f'Task is not paused (Status: {task.status}).', 'warning')
            return redirect(url_for('settings.index', tab='historical'))

        # Resume the download
        downloader = HistoricalDataDownloader(task_id)
        downloader.start_download()

        flash('Download resumed successfully.', 'success')
        current_app.logger.info(f'User {current_user.username} resumed download task {task_id}')

    except Exception as e:
        flash(f'Error resuming download: {str(e)}', 'danger')
        current_app.logger.error(f'Error resuming download: {str(e)}')

    return redirect(url_for('settings.index', tab='historical'))


@settings_bp.route('/historical-data/cancel-download/<int:task_id>', methods=['POST'])
@login_required
def cancel_download(task_id):
    """Cancel a running or paused download task"""
    try:
        from app.download_service import active_downloads

        # Verify task belongs to user
        task = DownloadTask.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

        if task.status not in ['running', 'paused']:
            flash(f'Task cannot be cancelled (Status: {task.status}).', 'warning')
            return redirect(url_for('settings.index', tab='historical'))

        # Cancel the download
        if task_id in active_downloads:
            downloader = active_downloads[task_id]
            downloader.cancel_download()
        else:
            # If not in active downloads, just update status
            task.status = 'cancelled'
            task.completed_at = datetime.utcnow()
            db.session.commit()

        flash('Download cancelled successfully.', 'success')
        current_app.logger.info(f'User {current_user.username} cancelled download task {task_id}')

    except Exception as e:
        flash(f'Error cancelling download: {str(e)}', 'danger')
        current_app.logger.error(f'Error cancelling download: {str(e)}')

    return redirect(url_for('settings.index', tab='historical'))


@settings_bp.route('/historical-data/force-reset', methods=['POST'])
@login_required
def force_reset_downloads():
    """Force reset all download tasks for current user - cancels all pending/running/paused tasks AND clears historical data"""
    try:
        from app.download_service import active_downloads

        # Get all non-completed tasks for this user
        pending_tasks = DownloadTask.query.filter_by(user_id=current_user.id).filter(
            DownloadTask.status.in_(['pending', 'running', 'paused'])
        ).all()

        reset_count = 0
        for task in pending_tasks:
            # Cancel active downloads
            if task.id in active_downloads:
                try:
                    downloader = active_downloads[task.id]
                    downloader.cancel_download()
                except Exception as e:
                    current_app.logger.warning(f'Error cancelling active download {task.id}: {e}')

            # Force status to cancelled
            task.status = 'cancelled'
            task.completed_at = datetime.utcnow()
            reset_count += 1

        # Clear all historical data
        deleted_count = HistoricalData.query.delete()

        db.session.commit()

        flash(f'Successfully reset {reset_count} download task(s) and cleared {deleted_count} historical data records. You can now start a fresh download.', 'success')
        current_app.logger.info(f'User {current_user.username} force reset {reset_count} download tasks and cleared {deleted_count} historical data records')

    except Exception as e:
        flash(f'Error resetting downloads: {str(e)}', 'danger')
        current_app.logger.error(f'Error force resetting downloads: {str(e)}')
        db.session.rollback()

    return redirect(url_for('settings.index', tab='historical'))


@settings_bp.route('/historical-data/status', methods=['GET'])
@login_required
def download_status():
    """Get current download status and storage stats"""
    try:
        from app.download_service import get_active_task, get_storage_stats

        # Get active task
        active_task = get_active_task(current_user.id)

        # Get storage stats
        storage_stats = get_storage_stats(current_user.id)

        # Get recent tasks
        recent_tasks = DownloadTask.query.filter_by(
            user_id=current_user.id
        ).order_by(DownloadTask.created_at.desc()).limit(5).all()

        return jsonify({
            'success': True,
            'active_task': active_task.to_dict() if active_task else None,
            'storage_stats': storage_stats,
            'recent_tasks': [task.to_dict() for task in recent_tasks],
            'eta_seconds': active_task.calculate_eta() if active_task else None
        })

    except Exception as e:
        current_app.logger.error(f'Error getting download status: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/historical-data/stock-coverage', methods=['GET'])
@login_required
def stock_coverage():
    """Get list of stocks with their download status"""
    try:
        # Get search and pagination parameters
        search = request.args.get('search', '').strip()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))

        # Query all NIFTY 500 stocks
        query = Instrument.query.filter_by(
            exchange='NSE',
            instrument_type='EQ',
            is_nifty500=True
        )

        # Apply search filter
        if search:
            query = query.filter(Instrument.tradingsymbol.ilike(f'%{search}%'))

        # Get paginated results
        pagination = query.order_by(Instrument.tradingsymbol).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Check which stocks have historical data (JSON schema)
        stocks_data = []
        for instrument in pagination.items:
            hist_data = HistoricalData.query.filter_by(
                tradingsymbol=instrument.tradingsymbol
            ).first()

            # Get record count and date range if has data
            has_data = hist_data is not None
            record_count = hist_data.get_candle_count() if hist_data else 0
            earliest_date, latest_date = hist_data.get_date_range() if hist_data else (None, None)

            stocks_data.append({
                'id': instrument.id,
                'symbol': instrument.tradingsymbol,
                'name': instrument.name,
                'has_data': has_data,
                'record_count': record_count,
                'earliest_date': earliest_date,
                'latest_date': latest_date
            })

        return jsonify({
            'success': True,
            'stocks': stocks_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next
            }
        })

    except Exception as e:
        current_app.logger.error(f'Error getting stock coverage: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# MARKET CAP DATA ROUTES
# ============================================================================

@settings_bp.route('/marketcap/start', methods=['POST'])
@login_required
def start_marketcap_fetch():
    """Start fetching market cap data from NSE for all stocks"""
    try:
        success, message, task_id = marketcap_service.start_marketcap_fetch(
            current_user.id,
            current_app._get_current_object()
        )

        if success:
            return jsonify({
                'success': True,
                'message': message,
                'task_id': task_id
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error starting market cap fetch: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/marketcap/status', methods=['GET'])
@login_required
def marketcap_fetch_status():
    """Get status of current market cap fetch task"""
    try:
        status = marketcap_service.get_marketcap_fetch_status(current_user.id)
        statistics = marketcap_service.get_marketcap_statistics()

        return jsonify({
            'success': True,
            'task': status,
            'statistics': statistics
        })

    except Exception as e:
        current_app.logger.error(f'Error getting market cap fetch status: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/marketcap/cancel/<int:task_id>', methods=['POST'])
@login_required
def cancel_marketcap_fetch(task_id):
    """Cancel a running market cap fetch task"""
    try:
        # Verify task belongs to current user
        task = MarketCapFetchTask.query.get(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': 'Task not found'
            }), 404

        if task.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Unauthorized'
            }), 403

        success, message = marketcap_service.cancel_marketcap_fetch(task_id)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error cancelling market cap fetch: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/marketcap/data', methods=['GET'])
@login_required
def get_marketcap_data():
    """Get paginated market cap data"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        search = request.args.get('search', '', type=str)

        # Build query
        query = StockInformation.query

        # Apply search filter
        if search:
            query = query.filter(
                db.or_(
                    StockInformation.tradingsymbol.like(f'%{search}%'),
                    StockInformation.company_name.like(f'%{search}%')
                )
            )

        # Paginate
        pagination = query.order_by(
            StockInformation.total_market_cap.desc().nullslast()
        ).paginate(page=page, per_page=per_page, error_out=False)

        # Convert to dict
        stocks_data = []
        for stock in pagination.items:
            stocks_data.append(stock.to_dict())

        return jsonify({
            'success': True,
            'stocks': stocks_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next
            }
        })

    except Exception as e:
        current_app.logger.error(f'Error getting market cap data: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================================================
# INDEX MANAGEMENT ROUTES
# ========================================================================

@settings_bp.route('/index_stats')
@login_required
def index_stats():
    """Get statistics about index history data"""
    try:
        from app.models import IndexHistory, Sector, SubSector
        from sqlalchemy import func

        # Count total index symbols (sectors + subsectors + market)
        sectors_with_symbol = Sector.query.filter(Sector.index_symbol != None).count()
        subsectors_with_symbol = SubSector.query.filter(SubSector.index_symbol != None).count()
        total_indices = sectors_with_symbol + subsectors_with_symbol + 1  # +1 for market

        # Count index data points
        data_points = IndexHistory.query.count()

        # Get date range
        earliest = db.session.query(func.min(IndexHistory.date)).scalar()
        latest = db.session.query(func.max(IndexHistory.date)).scalar()

        return jsonify({
            'success': True,
            'total_indices': total_indices,
            'data_points': data_points,
            'earliest_date': earliest.isoformat() if earliest else None,
            'latest_date': latest.isoformat() if latest else None
        })
    except Exception as e:
        current_app.logger.error(f'Error getting index stats: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/generate_indices', methods=['POST'])
@login_required
def generate_indices():
    """Generate historical indices for all sectors and subsectors"""
    try:
        from app.historical_index_service import HistoricalIndexService
        from datetime import date

        data = request.get_json()
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')

        if not start_date_str or not end_date_str:
            return jsonify({
                'success': False,
                'error': 'Start date and end date are required'
            }), 400

        # Parse dates
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)

        # Validate dates
        if start_date > end_date:
            return jsonify({
                'success': False,
                'error': 'Start date must be before end date'
            }), 400

        current_app.logger.info(f'Generating indices from {start_date} to {end_date}')

        # Generate indices (this is synchronous for now - could be made async later)
        result = HistoricalIndexService.generate_all_indices(start_date, end_date)

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Error generating indices: {str(e)}')
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/generate_index_symbols', methods=['POST'])
@login_required
def generate_index_symbols():
    """Automatically generate index symbols for all sectors and subsectors"""
    try:
        from app.models import Sector, SubSector
        import re

        current_app.logger.info('Auto-generating index symbols for all sectors and subsectors')

        sectors_updated = 0
        subsectors_updated = 0

        # Generate symbols for sectors
        sectors = Sector.query.filter_by(is_active=True).all()
        for sector in sectors:
            if not sector.index_symbol:
                # Create symbol from name: remove special chars, take first 8 chars, uppercase
                symbol = re.sub(r'[^A-Za-z0-9]', '', sector.name).upper()[:8]

                # Ensure uniqueness
                counter = 1
                original_symbol = symbol
                while Sector.query.filter_by(index_symbol=symbol).first():
                    symbol = f"{original_symbol[:6]}{counter:02d}"
                    counter += 1

                sector.index_symbol = symbol
                sectors_updated += 1
                current_app.logger.info(f'Generated symbol for sector {sector.name}: {symbol}')

        # Generate symbols for subsectors
        subsectors = SubSector.query.filter_by(is_active=True).all()
        for subsector in subsectors:
            if not subsector.index_symbol:
                # Create symbol from name: remove special chars, take first 8 chars, uppercase
                symbol = re.sub(r'[^A-Za-z0-9]', '', subsector.name).upper()[:8]

                # Ensure uniqueness
                counter = 1
                original_symbol = symbol
                while SubSector.query.filter_by(index_symbol=symbol).first():
                    symbol = f"{original_symbol[:6]}{counter:02d}"
                    counter += 1

                subsector.index_symbol = symbol
                subsectors_updated += 1
                current_app.logger.info(f'Generated symbol for subsector {subsector.name}: {symbol}')

        db.session.commit()

        flash(
            f'Successfully generated index symbols: {sectors_updated} sectors, {subsectors_updated} subsectors',
            'success'
        )

        return redirect(url_for('settings.index', active_tab='indices'))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error generating index symbols: {str(e)}')
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash(f'Error generating index symbols: {str(e)}', 'danger')
        return redirect(url_for('settings.index', active_tab='indices'))


@settings_bp.route('/clear_index_data', methods=['POST'])
@login_required
def clear_index_data():
    """Clear all index history data"""
    try:
        from app.historical_index_service import HistoricalIndexService

        current_app.logger.info('Clearing all index history data')

        result = HistoricalIndexService.clear_index_history()

        if result['success']:
            flash(f'Successfully cleared {result["deleted_count"]} index records', 'success')
        else:
            flash(f'Error clearing index data: {result.get("error")}', 'danger')

        return redirect(url_for('settings.index', active_tab='indices'))

    except Exception as e:
        current_app.logger.error(f'Error clearing index data: {str(e)}')
        flash(f'Error clearing index data: {str(e)}', 'danger')
        return redirect(url_for('settings.index', active_tab='indices'))


# ============================================================================
# FILES & STORAGE MANAGEMENT ROUTES
# ============================================================================

@settings_bp.route('/storage/analyze', methods=['GET'])
@login_required
def analyze_storage():
    """Analyze project storage usage"""
    try:
        from app.storage_service import StorageService

        storage = StorageService()
        stats = storage.analyze_storage()

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        current_app.logger.error(f'Error analyzing storage: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/storage/organization-status', methods=['GET'])
@login_required
def get_organization_status():
    """Get project organization status"""
    try:
        from app.storage_service import StorageService

        storage = StorageService()
        status = storage.check_organization_status()

        return jsonify({
            'success': True,
            'status': status
        })

    except Exception as e:
        current_app.logger.error(f'Error checking organization status: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/storage/organize-project', methods=['POST'])
@login_required
def organize_project():
    """Organize project files into proper directories"""
    try:
        from app.storage_service import StorageService

        data = request.get_json() or {}
        dry_run = data.get('dry_run', False)

        storage = StorageService()
        results = storage.organize_project(dry_run=dry_run)

        if results['success']:
            if not dry_run:
                flash(f'Successfully organized project: {len(results["moved_files"])} files moved', 'success')
            return jsonify({
                'success': True,
                'results': results
            })
        else:
            return jsonify({
                'success': False,
                'error': results['message'],
                'results': results
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error organizing project: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/storage/clean-temp', methods=['POST'])
@login_required
def clean_temp_files():
    """Clean temporary files"""
    try:
        from app.storage_service import StorageService

        data = request.get_json() or {}
        dry_run = data.get('dry_run', False)

        storage = StorageService()
        results = storage.clean_temp_files(dry_run=dry_run)

        if results['success']:
            if not dry_run and len(results['deleted_files']) > 0:
                flash(f'Cleaned {len(results["deleted_files"])} temporary files', 'success')
            return jsonify({
                'success': True,
                'results': results
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to clean temp files',
                'results': results
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error cleaning temp files: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/storage/clean-logs', methods=['POST'])
@login_required
def clean_old_logs():
    """Clean or archive old log files"""
    try:
        from app.storage_service import StorageService

        data = request.get_json() or {}
        dry_run = data.get('dry_run', False)
        days_to_keep = data.get('days', 7)

        storage = StorageService()
        results = storage.clean_old_logs(days_to_keep=days_to_keep, dry_run=dry_run)

        if results['success']:
            if not dry_run and results['deleted_lines'] > 0:
                flash(f'Cleaned {results["deleted_lines"]} old log entries', 'success')
            return jsonify({
                'success': True,
                'results': results
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to clean logs',
                'results': results
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error cleaning logs: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/storage/clean-backups', methods=['POST'])
@login_required
def clean_old_backups():
    """Clean old backup files"""
    try:
        from app.storage_service import StorageService

        data = request.get_json() or {}
        dry_run = data.get('dry_run', False)
        keep_count = data.get('keep', 5)

        storage = StorageService()
        results = storage.clean_old_backups(keep_count=keep_count, dry_run=dry_run)

        if results['success']:
            if not dry_run and len(results['deleted_files']) > 0:
                flash(f'Cleaned {len(results["deleted_files"])} old backup files', 'success')
            return jsonify({
                'success': True,
                'results': results
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to clean backups',
                'results': results
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error cleaning backups: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/storage/vacuum-db', methods=['POST'])
@login_required
def vacuum_database():
    """Vacuum SQLite database to reclaim space"""
    try:
        from app.storage_service import StorageService

        storage = StorageService()
        results = storage.vacuum_database()

        if results['success']:
            space_freed_mb = results['space_freed'] / (1024 * 1024)
            flash(f'Database optimized. Space freed: {space_freed_mb:.2f} MB', 'success')
            return jsonify({
                'success': True,
                'results': results
            })
        else:
            return jsonify({
                'success': False,
                'error': results.get('errors', ['Unknown error'])[0],
                'results': results
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error vacuuming database: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# HISTORICAL DATA SYNC ROUTES
# ============================================================================

@settings_bp.route('/historical-data/sync-latest', methods=['POST'])
@login_required
def sync_latest_candles():
    """Sync latest candlestick data for all stocks from Kite API"""
    try:
        from app.sync_service import start_sync_task

        # Check if user has Kite connection
        if not current_user.kite_connected or not current_user.kite_access_token:
            return jsonify({
                'success': False,
                'error': 'Please connect to Zerodha Kite first before syncing data.'
            }), 400

        # Verify Kite token is valid
        if not current_user.is_kite_token_valid():
            return jsonify({
                'success': False,
                'error': 'Your Kite access token has expired. Please reconnect to Kite.'
            }), 400

        # Start sync task
        success, message, task_id = start_sync_task(
            current_user.id,
            current_app._get_current_object()
        )

        if success:
            return jsonify({
                'success': True,
                'message': message,
                'task_id': task_id
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error starting sync task: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/historical-data/sync-status', methods=['GET'])
@login_required
def sync_status():
    """Get status of current sync task"""
    try:
        from app.sync_service import get_sync_status

        status = get_sync_status(current_user.id)

        return jsonify({
            'success': True,
            'status': status
        })

    except Exception as e:
        current_app.logger.error(f'Error getting sync status: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/historical-data/cancel-sync/<int:task_id>', methods=['POST'])
@login_required
def cancel_sync(task_id):
    """Cancel a running sync task"""
    try:
        from app.sync_service import cancel_sync_task
        from app.models import SyncTask

        # Verify task belongs to current user
        task = SyncTask.query.get(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': 'Task not found'
            }), 404

        if task.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Unauthorized'
            }), 403

        success, message = cancel_sync_task(task_id)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error cancelling sync task: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# STAGE ANALYSIS ROUTES
# ============================================================================

@settings_bp.route('/stage-analysis/run', methods=['POST'])
@login_required
def run_stage_analysis():
    """Run stage analysis for all sectors and subsectors"""
    try:
        from app.stage_analysis_service import start_stage_analysis

        # Start stage analysis task
        success, message, task_id = start_stage_analysis(
            current_user.id,
            current_app._get_current_object()
        )

        if success:
            return jsonify({
                'success': True,
                'message': message,
                'task_id': task_id
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error starting stage analysis: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/stage-analysis/status', methods=['GET'])
@login_required
def stage_analysis_status():
    """Get status of current stage analysis task"""
    try:
        from app.stage_analysis_service import get_stage_analysis_status

        status = get_stage_analysis_status(current_user.id)

        return jsonify({
            'success': True,
            'status': status
        })

    except Exception as e:
        current_app.logger.error(f'Error getting stage analysis status: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/stage-analysis/cancel/<int:task_id>', methods=['POST'])
@login_required
def cancel_stage_analysis(task_id):
    """Cancel a running stage analysis task"""
    try:
        from app.stage_analysis_service import cancel_stage_analysis as cancel_task
        from app.models import StageAnalysisTask

        # Verify task belongs to current user
        task = StageAnalysisTask.query.get(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': 'Task not found'
            }), 404

        if task.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Unauthorized'
            }), 403

        success, message = cancel_task(task_id)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error cancelling stage analysis: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
