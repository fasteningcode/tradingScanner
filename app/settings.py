import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app, session
from flask_login import login_required, current_user, logout_user
from werkzeug.utils import secure_filename
from app import db
from app.models import User
from app.forms import BackupForm, RestoreDatabaseForm, EmergencyRestoreForm

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

# Simple in-memory rate limiting for emergency restore
emergency_restore_attempts = {}


@settings_bp.route('/')
@settings_bp.route('/<tab>')
@login_required
def index(tab='general'):
    """Settings page with tabbed interface"""
    valid_tabs = ['general', 'backup', 'security', 'about']
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

    return render_template('settings/index.html',
                         title='Settings',
                         active_tab=tab,
                         app_info=app_info,
                         backup_form=backup_form,
                         restore_form=restore_form)


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
