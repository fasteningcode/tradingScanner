import os
import shutil
import sqlite3
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.forms import RestoreDatabaseForm

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


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
        'users_count': db.session.query(db.func.count(db.text('*'))).select_from(db.text('users')).scalar()
    }

    form = RestoreDatabaseForm()

    return render_template('settings/index.html',
                         title='Settings',
                         active_tab=tab,
                         app_info=app_info,
                         form=form)


@settings_bp.route('/backup', methods=['POST'])
@login_required
def backup_database():
    """Create and download database backup"""
    try:
        # Get the database file path
        db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        db_full_path = os.path.join(os.path.dirname(current_app.root_path), db_path)

        if not os.path.exists(db_full_path):
            flash('Database file not found.', 'danger')
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
            db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            db_full_path = os.path.join(os.path.dirname(current_app.root_path), db_path)

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
