from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, RadioField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from app.models import User


class LoginForm(FlaskForm):
    """Login form for user authentication"""

    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Please enter a valid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    """Registration form for new users"""

    username = StringField('Username', validators=[
        DataRequired(message='Username is required'),
        Length(min=3, max=80, message='Username must be between 3 and 80 characters')
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Please enter a valid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

    def validate_username(self, username):
        """Check if username is already taken"""
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Username already exists. Please choose a different one.')

    def validate_email(self, email):
        """Check if email is already registered"""
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Email already registered. Please use a different email address.')


class ChangePasswordForm(FlaskForm):
    """Form for changing user password"""

    current_password = PasswordField('Current Password', validators=[
        DataRequired(message='Please enter your current password')
    ])
    new_password = PasswordField('New Password', validators=[
        DataRequired(message='Please enter a new password'),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message='Please confirm your new password'),
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Change Password')


class BackupForm(FlaskForm):
    """Form for database backup with CSRF protection"""
    submit = SubmitField('Download Backup')


class RestoreDatabaseForm(FlaskForm):
    """Form for restoring database from backup"""

    database_file = FileField('Database File', validators=[
        FileRequired(message='Please select a database file'),
        FileAllowed(['db', 'sqlite', 'sqlite3'], 'Only .db, .sqlite, or .sqlite3 files are allowed')
    ])
    password = PasswordField('Confirm Password', validators=[
        DataRequired(message='Password is required to restore database')
    ])
    submit = SubmitField('Restore Database')


class EmergencyRestoreForm(FlaskForm):
    """Form for emergency database restore with emergency password"""

    database_file = FileField('Database File', validators=[
        FileRequired(message='Please select a database file'),
        FileAllowed(['db', 'sqlite', 'sqlite3'], 'Only .db, .sqlite, or .sqlite3 files are allowed')
    ])
    emergency_password = PasswordField('Emergency Restore Password', validators=[
        DataRequired(message='Emergency restore password is required')
    ])
    submit = SubmitField('Emergency Restore Database')


class KiteCredentialsForm(FlaskForm):
    """Form for manually updating Kite Connect credentials"""

    access_token = StringField('Access Token', validators=[
        DataRequired(message='Access token is required')
    ])
    user_id = StringField('User ID', validators=[
        DataRequired(message='User ID is required')
    ])
    public_token = StringField('Public Token')
    refresh_token = StringField('Refresh Token')
    submit = SubmitField('Update Credentials')


class ScannerProfileForm(FlaskForm):
    """Form for creating/editing scanner profiles"""

    name = StringField('Profile Name', validators=[
        DataRequired(message='Profile name is required'),
        Length(min=3, max=100, message='Name must be between 3 and 100 characters')
    ])
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=500, message='Description cannot exceed 500 characters')
    ])
    scan_level = RadioField('Scan Level',
        choices=[('stage', 'Stage Level'), ('sector', 'Sector Level'), ('subsector', 'Subsector Level')],
        default='stage',
        validators=[DataRequired(message='Please select a scan level')]
    )
    criteria_json = HiddenField('Criteria JSON')
    is_default = BooleanField('Set as Default Profile')

    # Enable/Disable toggles (stored in criteria_json, not as separate fields)
    # enable_scan_level_filter - whether to use stage/sector/subsector filtering
    # enable_rs_filter - whether to use RS filtering

    submit = SubmitField('Save Profile')
