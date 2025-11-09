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
from app.models import ScannerProfile, ScannerTask, ScanResult, Sector, SubSector, Instrument
from app.forms import ScannerProfileForm
from app import scanner_service
from datetime import datetime
import json

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
                # Get sector/subsector data for re-rendering
                sectors_data = _get_sectors_subsectors_data()
                return render_template('scanner/profile_form.html',
                                     title='Create Scanner Profile',
                                     form=form,
                                     action='create',
                                     **sectors_data)

            # Parse criteria JSON from hidden field
            criteria_json = form.criteria_json.data or '{}'

            # Validate JSON
            try:
                criteria_dict = json.loads(criteria_json)
            except json.JSONDecodeError:
                criteria_dict = {}

            # Create new profile
            profile = ScannerProfile(
                user_id=current_user.id,
                name=form.name.data,
                description=form.description.data,
                criteria=json.dumps(criteria_dict),
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

    # Get sector/subsector data for rendering
    sectors_data = _get_sectors_subsectors_data()

    return render_template('scanner/profile_form.html',
                         title='Create Scanner Profile',
                         form=form,
                         action='create',
                         **sectors_data)


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

    # Pre-populate form with existing criteria on GET request
    if request.method == 'GET':
        # Parse existing criteria
        try:
            criteria = json.loads(profile.criteria) if profile.criteria else {}
            form.scan_level.data = criteria.get('scan_level', 'subsector')
            form.criteria_json.data = profile.criteria
        except json.JSONDecodeError:
            form.criteria_json.data = '{}'

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
                    # Get sector/subsector data for re-rendering
                    sectors_data = _get_sectors_subsectors_data()
                    return render_template('scanner/profile_form.html',
                                         title='Edit Scanner Profile',
                                         form=form,
                                         action='edit',
                                         profile=profile,
                                         **sectors_data)

            # Parse criteria JSON from hidden field
            criteria_json = form.criteria_json.data or '{}'

            # Validate JSON
            try:
                criteria_dict = json.loads(criteria_json)
            except json.JSONDecodeError:
                criteria_dict = {}

            # Update profile
            profile.name = form.name.data
            profile.description = form.description.data
            profile.criteria = json.dumps(criteria_dict)
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

    # Get sector/subsector data for rendering
    sectors_data = _get_sectors_subsectors_data()

    return render_template('scanner/profile_form.html',
                         title='Edit Scanner Profile',
                         form=form,
                         action='edit',
                         profile=profile,
                         **sectors_data)


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


# Helper Functions

def _get_sectors_subsectors_data():
    """
    Helper function to get sectors and subsectors grouped by stage
    Returns dictionary with sectors_by_stage and subsectors_by_sector_and_stage
    """
    # Get all active sectors ordered by display_order and name
    sectors = Sector.query.filter_by(is_active=True).order_by(
        Sector.display_order, Sector.name
    ).all()

    # Get all active subsectors
    subsectors = SubSector.query.filter_by(is_active=True).order_by(
        SubSector.display_order, SubSector.name
    ).all()

    # Group sectors by stage
    sectors_by_stage = {1: [], 2: [], 3: [], 4: [], None: []}
    for sector in sectors:
        stage = sector.current_stage
        if stage not in sectors_by_stage:
            sectors_by_stage[stage] = []
        sectors_by_stage[stage].append(sector)

    # Group subsectors by sector and then by stage
    subsectors_by_sector = {}
    for subsector in subsectors:
        sector_id = subsector.sector_id
        if sector_id not in subsectors_by_sector:
            subsectors_by_sector[sector_id] = {1: [], 2: [], 3: [], 4: [], None: []}

        stage = subsector.current_stage
        if stage not in subsectors_by_sector[sector_id]:
            subsectors_by_sector[sector_id][stage] = []
        subsectors_by_sector[sector_id][stage].append(subsector)

    # Get stock counts for each sector and subsector
    sector_stock_counts = {}
    for sector in sectors:
        # Count NIFTY 500 stocks in this sector via subsectors
        count = db.session.query(Instrument).join(
            SubSector, Instrument.sub_sector_id == SubSector.id
        ).filter(
            SubSector.sector_id == sector.id,
            Instrument.is_nifty500 == True,
            Instrument.exchange == 'NSE',
            Instrument.instrument_type == 'EQ'
        ).count()
        sector_stock_counts[sector.id] = count

    subsector_stock_counts = {}
    for subsector in subsectors:
        count = Instrument.query.filter_by(
            sub_sector_id=subsector.id,
            is_nifty500=True,
            exchange='NSE',
            instrument_type='EQ'
        ).count()
        subsector_stock_counts[subsector.id] = count

    # Calculate sector counts per stage (how many sectors are in each stage)
    stage_sector_counts = {}
    for stage in [1, 2, 3, 4]:
        stage_sector_counts[stage] = len(sectors_by_stage.get(stage, []))

    return {
        'sectors_by_stage': sectors_by_stage,
        'subsectors_by_sector': subsectors_by_sector,
        'sector_stock_counts': sector_stock_counts,
        'subsector_stock_counts': subsector_stock_counts,
        'stage_sector_counts': stage_sector_counts,
        'all_sectors': sectors
    }
