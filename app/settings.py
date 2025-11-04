import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app, session, jsonify
from flask_login import login_required, current_user, logout_user
from werkzeug.utils import secure_filename
from app import db
from app.models import User, HistoricalDataSettings, HistoricalData, DownloadTask, DownloadLog, Instrument
from app.forms import BackupForm, RestoreDatabaseForm, EmergencyRestoreForm, KiteCredentialsForm
from app.kite_auth import get_kite_client

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


@settings_bp.route('/historical-data/clear', methods=['POST'])
@login_required
def clear_historical_data():
    """Clear all historical data from the database"""
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
    try:
        from app.download_service import create_download_task, get_active_task, HistoricalDataDownloader

        # Check if there's already an active task
        active_task = get_active_task(current_user.id)
        if active_task:
            flash(f'You already have an active download task (Status: {active_task.status}).', 'warning')
            return redirect(url_for('settings.index', tab='historical'))

        # Create new task
        task = create_download_task(current_user.id)
        if not task:
            flash('Please configure historical data settings first.', 'warning')
            return redirect(url_for('settings.index', tab='historical'))

        # Start download in background
        downloader = HistoricalDataDownloader(task.id)
        downloader.start_download()

        flash('Historical data download started in background!', 'success')
        current_app.logger.info(f'User {current_user.username} started download task {task.id}')

    except Exception as e:
        flash(f'Error starting download: {str(e)}', 'danger')
        current_app.logger.error(f'Error starting download: {str(e)}')

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

        # Check which stocks have historical data
        stocks_data = []
        for instrument in pagination.items:
            has_data = HistoricalData.query.filter_by(
                instrument_id=instrument.id
            ).first() is not None

            # Get record count and date range if has data
            record_count = 0
            earliest_date = None
            latest_date = None

            if has_data:
                record_count = HistoricalData.query.filter_by(
                    instrument_id=instrument.id
                ).count()

                earliest = db.session.query(db.func.min(HistoricalData.timestamp)).filter_by(
                    instrument_id=instrument.id
                ).scalar()
                latest = db.session.query(db.func.max(HistoricalData.timestamp)).filter_by(
                    instrument_id=instrument.id
                ).scalar()

                earliest_date = earliest.isoformat() if earliest else None
                latest_date = latest.isoformat() if latest else None

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
