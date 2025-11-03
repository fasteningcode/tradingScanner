from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User
from app.forms import LoginForm, RegistrationForm, ChangePasswordForm

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login route"""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = LoginForm()

    if form.validate_on_submit():
        # Find user by email
        user = User.query.filter_by(email=form.email.data).first()

        # Check if user exists and password is correct
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password. Please try again.', 'danger')
            return redirect(url_for('auth.login'))

        # Check if user account is active
        if not user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'warning')
            return redirect(url_for('auth.login'))

        # Log the user in
        login_user(user, remember=form.remember_me.data)
        user.update_last_login()

        flash(f'Welcome back, {user.username}!', 'success')

        # Redirect to next page or dashboard
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html', title='Sign In', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route"""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = RegistrationForm()

    if form.validate_on_submit():
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data
        )
        user.set_password(form.password.data)

        # Add user to database
        db.session.add(user)
        db.session.commit()

        flash('Congratulations! Your account has been created. You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', title='Register', form=form)


@auth_bp.route('/logout')
def logout():
    """User logout route"""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password route for authenticated users"""
    form = ChangePasswordForm()

    if form.validate_on_submit():
        # Verify current password is correct
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect. Please try again.', 'danger')
            return redirect(url_for('auth.change_password'))

        # Check if new password is different from current password
        if current_user.check_password(form.new_password.data):
            flash('New password must be different from your current password.', 'warning')
            return redirect(url_for('auth.change_password'))

        # Update password
        current_user.set_password(form.new_password.data)
        db.session.commit()

        flash('Your password has been changed successfully!', 'success')
        return redirect(url_for('dashboard.profile'))

    return render_template('auth/change_password.html', title='Change Password', form=form)
