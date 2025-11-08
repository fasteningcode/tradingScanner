"""
Scanner Routes

Routes for stock scanner feature including:
- Main scanner interface
- Profile management
- Scan execution and results
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import ScannerProfile, ScannerTask, ScanResult
from app.forms import ScannerProfileForm
from app import scanner_service
from datetime import datetime

scanner_bp = Blueprint('scanner', __name__, url_prefix='/scanner')


@scanner_bp.route('/')
@scanner_bp.route('/<tab>')
@login_required
def index(tab='scanner'):
    """
    Scanner main page with tabs

    Tabs:
    - scanner: Main scanning interface
    - profiles: Profile management
    - results: Scan results history
    """
    valid_tabs = ['scanner', 'profiles', 'results']
    if tab not in valid_tabs:
        tab = 'scanner'

    # Get user's scanner profiles
    profiles = scanner_service.get_user_profiles(current_user.id)
    default_profile = scanner_service.get_default_profile(current_user.id)

    # Get recent scanner tasks
    recent_tasks = ScannerTask.query.filter_by(user_id=current_user.id).order_by(
        ScannerTask.created_at.desc()
    ).limit(10).all()

    # Get current scan status
    current_scan = scanner_service.get_scan_status(current_user.id)

    return render_template(
        'scanner/index.html',
        title='Stock Scanner',
        active_tab=tab,
        profiles=profiles,
        default_profile=default_profile,
        recent_tasks=recent_tasks,
        current_scan=current_scan
    )


@scanner_bp.route('/profiles/create', methods=['GET', 'POST'])
@login_required
def create_profile():
    """Create a new scanner profile"""
    form = ScannerProfileForm()

    if form.validate_on_submit():
        try:
            # Check if profile with same name already exists for this user
            existing = ScannerProfile.query.filter_by(
                user_id=current_user.id,
                name=form.name.data
            ).first()

            if existing:
                flash(f'A profile named "{form.name.data}" already exists.', 'warning')
                return render_template('scanner/profile_form.html',
                                     title='Create Scanner Profile',
                                     form=form,
                                     action='create')

            # Create new profile
            profile = ScannerProfile(
                user_id=current_user.id,
                name=form.name.data,
                description=form.description.data,
                criteria='{}',  # Empty JSON for now, will be populated later
                is_default=form.is_default.data
            )

            # If setting as default, unset other defaults
            if profile.is_default:
                ScannerProfile.query.filter_by(
                    user_id=current_user.id,
                    is_default=True
                ).update({'is_default': False})

            db.session.add(profile)
            db.session.commit()

            flash(f'Scanner profile "{profile.name}" created successfully!', 'success')
            return redirect(url_for('scanner.index', tab='profiles'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating profile: {str(e)}', 'danger')
            current_app.logger.error(f'Error creating scanner profile: {str(e)}', exc_info=True)

    return render_template('scanner/profile_form.html',
                         title='Create Scanner Profile',
                         form=form,
                         action='create')


@scanner_bp.route('/profiles/<int:profile_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_profile(profile_id):
    """Edit an existing scanner profile"""
    # Verify profile belongs to user
    profile = ScannerProfile.query.filter_by(
        id=profile_id,
        user_id=current_user.id
    ).first_or_404()

    form = ScannerProfileForm(obj=profile)

    if form.validate_on_submit():
        try:
            # Check if new name conflicts with another profile
            if form.name.data != profile.name:
                existing = ScannerProfile.query.filter_by(
                    user_id=current_user.id,
                    name=form.name.data
                ).first()

                if existing:
                    flash(f'A profile named "{form.name.data}" already exists.', 'warning')
                    return render_template('scanner/profile_form.html',
                                         title='Edit Scanner Profile',
                                         form=form,
                                         action='edit',
                                         profile=profile)

            # Update profile
            profile.name = form.name.data
            profile.description = form.description.data
            profile.updated_at = datetime.utcnow()

            # Handle default status
            if form.is_default.data and not profile.is_default:
                # Setting as default, unset others
                ScannerProfile.query.filter_by(
                    user_id=current_user.id,
                    is_default=True
                ).update({'is_default': False})
                profile.is_default = True
            elif not form.is_default.data and profile.is_default:
                # Unsetting default
                profile.is_default = False

            db.session.commit()

            flash(f'Scanner profile "{profile.name}" updated successfully!', 'success')
            return redirect(url_for('scanner.index', tab='profiles'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'danger')
            current_app.logger.error(f'Error updating scanner profile: {str(e)}', exc_info=True)

    return render_template('scanner/profile_form.html',
                         title='Edit Scanner Profile',
                         form=form,
                         action='edit',
                         profile=profile)


@scanner_bp.route('/profiles/<int:profile_id>/delete', methods=['POST'])
@login_required
def delete_profile(profile_id):
    """Delete a scanner profile"""
    try:
        success = scanner_service.delete_profile(current_user.id, profile_id)

        if success:
            flash('Scanner profile deleted successfully.', 'success')
        else:
            flash('Profile not found or could not be deleted.', 'warning')

    except Exception as e:
        flash(f'Error deleting profile: {str(e)}', 'danger')
        current_app.logger.error(f'Error deleting scanner profile: {str(e)}', exc_info=True)

    return redirect(url_for('scanner.index', tab='profiles'))


@scanner_bp.route('/profiles/<int:profile_id>/set-default', methods=['POST'])
@login_required
def set_default_profile(profile_id):
    """Set a profile as the default"""
    try:
        success = scanner_service.set_default_profile(current_user.id, profile_id)

        if success:
            flash('Default profile updated successfully.', 'success')
        else:
            flash('Profile not found or could not be set as default.', 'warning')

    except Exception as e:
        flash(f'Error setting default profile: {str(e)}', 'danger')
        current_app.logger.error(f'Error setting default profile: {str(e)}', exc_info=True)

    return redirect(url_for('scanner.index', tab='profiles'))


@scanner_bp.route('/scan/start', methods=['POST'])
@login_required
def start_scan():
    """Start a new scan (AJAX)"""
    try:
        data = request.get_json() or {}
        profile_id = data.get('profile_id')

        if not profile_id:
            return jsonify({
                'success': False,
                'error': 'Profile ID is required'
            }), 400

        # Verify profile belongs to user
        profile = ScannerProfile.query.filter_by(
            id=profile_id,
            user_id=current_user.id
        ).first()

        if not profile:
            return jsonify({
                'success': False,
                'error': 'Profile not found'
            }), 404

        # Start scan task
        task_id = scanner_service.start_scan(
            current_user.id,
            profile_id,
            current_app._get_current_object()
        )

        if task_id:
            return jsonify({
                'success': True,
                'message': 'Scan started successfully',
                'task_id': task_id
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to start scan'
            }), 500

    except Exception as e:
        current_app.logger.error(f'Error starting scan: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scanner_bp.route('/scan/status', methods=['GET'])
@login_required
def scan_status():
    """Get current scan status (AJAX)"""
    try:
        status = scanner_service.get_scan_status(current_user.id)

        return jsonify({
            'success': True,
            'status': status,
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        current_app.logger.error(f'Error getting scan status: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scanner_bp.route('/scan/<int:task_id>/cancel', methods=['POST'])
@login_required
def cancel_scan(task_id):
    """Cancel a running scan"""
    try:
        # Verify task belongs to user
        task = ScannerTask.query.filter_by(
            id=task_id,
            user_id=current_user.id
        ).first()

        if not task:
            return jsonify({
                'success': False,
                'error': 'Task not found'
            }), 404

        success = scanner_service.cancel_scan(task_id)

        if success:
            return jsonify({
                'success': True,
                'message': 'Scan cancelled successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Could not cancel scan'
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error cancelling scan: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scanner_bp.route('/results', methods=['GET'])
@login_required
def get_results():
    """Get scan results with pagination (AJAX)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        task_id = request.args.get('task_id', type=int)

        query = ScannerTask.query.filter_by(user_id=current_user.id)

        if task_id:
            query = query.filter_by(id=task_id)

        pagination = query.order_by(
            ScannerTask.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        tasks = [task.to_dict() for task in pagination.items]

        return jsonify({
            'success': True,
            'tasks': tasks,
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
        current_app.logger.error(f'Error getting results: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
