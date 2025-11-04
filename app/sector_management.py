"""
Sector Management Blueprint
Provides comprehensive CRUD operations for Sectors, SubSectors, and Stock assignments
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Sector, SubSector, Instrument
from app.sector_service import SectorService
from app.subsector_service import SubSectorService

sector_management_bp = Blueprint('sector_management', __name__, url_prefix='/sector-management')


# ============================================================================
# DASHBOARD & OVERVIEW ROUTES
# ============================================================================

@sector_management_bp.route('/')
@login_required
def index():
    """Main sector management dashboard"""
    # Get all sectors with their sub-sectors
    sectors = SectorService.get_all_sectors(include_inactive=False, order_by='display_order')

    # Get statistics
    total_sectors = len(sectors)
    total_subsectors = SubSector.query.filter_by(is_active=True).count()

    # Count assigned vs unassigned NIFTY 500 stocks
    assigned_stocks = Instrument.query.filter(
        Instrument.exchange == 'NSE',
        Instrument.instrument_type == 'EQ',
        Instrument.is_nifty500 == True,
        Instrument.sub_sector_id.isnot(None)
    ).count()

    unassigned_stocks = Instrument.query.filter(
        Instrument.exchange == 'NSE',
        Instrument.instrument_type == 'EQ',
        Instrument.is_nifty500 == True,
        Instrument.sub_sector_id.is_(None)
    ).count()

    return render_template('sector_management/index.html',
                         title='Sector Management',
                         sectors=sectors,
                         total_sectors=total_sectors,
                         total_subsectors=total_subsectors,
                         assigned_stocks=assigned_stocks,
                         unassigned_stocks=unassigned_stocks)


# ============================================================================
# SECTOR CRUD ROUTES
# ============================================================================

@sector_management_bp.route('/sectors/create', methods=['GET', 'POST'])
@login_required
def create_sector():
    """Create a new sector"""
    from flask import current_app

    current_app.logger.info(f"=== CREATE SECTOR REQUEST ===")
    current_app.logger.info(f"Method: {request.method}")
    current_app.logger.info(f"User: {current_user.username if current_user.is_authenticated else 'Anonymous'}")

    if request.method == 'POST':
        current_app.logger.info("POST request received for sector creation")
        current_app.logger.info(f"Form data: {dict(request.form)}")
        current_app.logger.info(f"CSRF Token in form: {'csrf_token' in request.form}")

        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip() or None
        icon = request.form.get('icon', '').strip() or None
        color = request.form.get('color', '').strip() or None
        display_order = request.form.get('display_order', 0, type=int)

        current_app.logger.info(f"Extracted values - Name: {name}, Icon: {icon}, Color: {color}, Order: {display_order}")

        sector, error = SectorService.create_sector(
            name=name,
            description=description,
            icon=icon,
            color=color,
            display_order=display_order
        )

        if error:
            current_app.logger.error(f"Sector creation failed: {error}")
            flash(f'Error creating sector: {error}', 'danger')
            return render_template('sector_management/sector_form.html',
                                 title='Create Sector',
                                 action='create')

        current_app.logger.info(f"Sector created successfully: {sector.name} (ID: {sector.id})")
        flash(f'Sector "{sector.name}" created successfully!', 'success')
        return redirect(url_for('sector_management.index'))

    current_app.logger.info("GET request - Rendering create form")
    return render_template('sector_management/sector_form.html',
                         title='Create Sector',
                         action='create')


@sector_management_bp.route('/sectors/<int:sector_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_sector(sector_id):
    """Edit an existing sector"""
    sector = SectorService.get_sector_by_id(sector_id, include_inactive=True)

    if not sector:
        flash('Sector not found', 'danger')
        return redirect(url_for('sector_management.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip() or None
        description = request.form.get('description', '').strip() or None
        icon = request.form.get('icon', '').strip() or None
        color = request.form.get('color', '').strip() or None
        is_active = request.form.get('is_active') == 'on'
        display_order = request.form.get('display_order', type=int)

        updated_sector, error = SectorService.update_sector(
            sector_id=sector_id,
            name=name,
            description=description,
            icon=icon,
            color=color,
            is_active=is_active,
            display_order=display_order
        )

        if error:
            flash(f'Error updating sector: {error}', 'danger')
        else:
            flash(f'Sector "{updated_sector.name}" updated successfully!', 'success')
            return redirect(url_for('sector_management.index'))

    return render_template('sector_management/sector_form.html',
                         title='Edit Sector',
                         action='edit',
                         sector=sector)


@sector_management_bp.route('/sectors/<int:sector_id>/delete', methods=['POST'])
@login_required
def delete_sector(sector_id):
    """Delete a sector (soft or hard)"""
    mode = request.form.get('mode', 'soft')  # 'soft' or 'hard'

    success, error = SectorService.delete_sector(sector_id, mode=mode)

    if error:
        flash(f'Error deleting sector: {error}', 'danger')
    else:
        if mode == 'soft':
            flash('Sector deactivated successfully', 'success')
        else:
            flash('Sector permanently deleted', 'warning')

    return redirect(url_for('sector_management.index'))


@sector_management_bp.route('/sectors/<int:sector_id>')
@login_required
def view_sector(sector_id):
    """View sector details with sub-sectors and statistics"""
    sector, sub_sectors = SectorService.get_sector_with_subsectors(sector_id)

    if not sector:
        flash('Sector not found', 'danger')
        return redirect(url_for('sector_management.index'))

    # Get statistics for each sub-sector
    subsector_data = []
    for subsector in sub_sectors:
        stock_count = subsector.instruments.filter_by(is_nifty500=True).count()
        subsector_data.append({
            'subsector': subsector,
            'stock_count': stock_count
        })

    return render_template('sector_management/view_sector.html',
                         title=f'{sector.name} - Sector Details',
                         sector=sector,
                         subsector_data=subsector_data)


# ============================================================================
# SUB-SECTOR CRUD ROUTES
# ============================================================================

@sector_management_bp.route('/sectors/<int:sector_id>/subsectors/create', methods=['GET', 'POST'])
@login_required
def create_subsector(sector_id):
    """Create a new sub-sector under a sector"""
    sector = SectorService.get_sector_by_id(sector_id)

    if not sector:
        flash('Sector not found', 'danger')
        return redirect(url_for('sector_management.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip() or None
        display_order = request.form.get('display_order', 0, type=int)

        subsector, error = SubSectorService.create_sub_sector(
            sector_id=sector_id,
            name=name,
            description=description,
            display_order=display_order
        )

        if error:
            flash(f'Error creating sub-sector: {error}', 'danger')
            return render_template('sector_management/subsector_form.html',
                                 title='Create Sub-Sector',
                                 action='create',
                                 sector=sector)

        flash(f'Sub-sector "{subsector.name}" created successfully!', 'success')
        return redirect(url_for('sector_management.view_sector', sector_id=sector_id))

    return render_template('sector_management/subsector_form.html',
                         title='Create Sub-Sector',
                         action='create',
                         sector=sector)


@sector_management_bp.route('/subsectors/<int:subsector_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_subsector(subsector_id):
    """Edit an existing sub-sector"""
    subsector = SubSectorService.get_sub_sector_by_id(subsector_id, include_inactive=True)

    if not subsector:
        flash('Sub-sector not found', 'danger')
        return redirect(url_for('sector_management.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip() or None
        description = request.form.get('description', '').strip() or None
        is_active = request.form.get('is_active') == 'on'
        display_order = request.form.get('display_order', type=int)

        updated_subsector, error = SubSectorService.update_sub_sector(
            sub_sector_id=subsector_id,
            name=name,
            description=description,
            is_active=is_active,
            display_order=display_order
        )

        if error:
            flash(f'Error updating sub-sector: {error}', 'danger')
        else:
            flash(f'Sub-sector "{updated_subsector.name}" updated successfully!', 'success')
            return redirect(url_for('sector_management.view_sector',
                                  sector_id=updated_subsector.sector_id))

    return render_template('sector_management/subsector_form.html',
                         title='Edit Sub-Sector',
                         action='edit',
                         subsector=subsector,
                         sector=subsector.sector)


@sector_management_bp.route('/subsectors/<int:subsector_id>/delete', methods=['POST'])
@login_required
def delete_subsector(subsector_id):
    """Delete a sub-sector (soft or hard)"""
    subsector = SubSectorService.get_sub_sector_by_id(subsector_id, include_inactive=True)

    if not subsector:
        flash('Sub-sector not found', 'danger')
        return redirect(url_for('sector_management.index'))

    sector_id = subsector.sector_id
    mode = request.form.get('mode', 'soft')  # 'soft' or 'hard'
    unassign_stocks = request.form.get('unassign_stocks') == 'on'

    success, error = SubSectorService.delete_sub_sector(
        sub_sector_id=subsector_id,
        mode=mode,
        unassign_stocks=unassign_stocks
    )

    if error:
        flash(f'Error deleting sub-sector: {error}', 'danger')
    else:
        if mode == 'soft':
            flash('Sub-sector deactivated successfully', 'success')
        else:
            flash('Sub-sector permanently deleted', 'warning')

    return redirect(url_for('sector_management.view_sector', sector_id=sector_id))


@sector_management_bp.route('/subsectors/<int:subsector_id>/stocks')
@login_required
def view_subsector_stocks(subsector_id):
    """View and manage stocks in a sub-sector"""
    subsector = SubSectorService.get_sub_sector_by_id(subsector_id)

    if not subsector:
        flash('Sub-sector not found', 'danger')
        return redirect(url_for('sector_management.index'))

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)

    # Get assigned stocks with pagination
    pagination = SubSectorService.get_stocks_by_subsector(
        sub_sector_id=subsector_id,
        search=search,
        page=page,
        per_page=50
    )

    return render_template('sector_management/subsector_stocks.html',
                         title=f'{subsector.name} - Stocks',
                         subsector=subsector,
                         pagination=pagination,
                         search=search)


# ============================================================================
# STOCK ASSIGNMENT API ROUTES (AJAX)
# ============================================================================

@sector_management_bp.route('/api/subsectors/<int:subsector_id>/assign-stocks', methods=['POST'])
@login_required
def api_assign_stocks(subsector_id):
    """API endpoint to assign stocks to a sub-sector"""
    try:
        data = request.get_json()
        instrument_ids = data.get('instrument_ids', [])

        if not instrument_ids:
            return jsonify({'success': False, 'error': 'No instruments selected'}), 400

        count, error = SubSectorService.assign_stocks(subsector_id, instrument_ids)

        if error:
            return jsonify({'success': False, 'error': error}), 400

        return jsonify({
            'success': True,
            'message': f'Successfully assigned {count} stock(s)',
            'count': count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@sector_management_bp.route('/api/subsectors/<int:subsector_id>/remove-stocks', methods=['POST'])
@login_required
def api_remove_stocks(subsector_id):
    """API endpoint to remove stocks from a sub-sector"""
    try:
        data = request.get_json()
        instrument_ids = data.get('instrument_ids', [])

        if not instrument_ids:
            return jsonify({'success': False, 'error': 'No instruments selected'}), 400

        count, error = SubSectorService.remove_stocks(subsector_id, instrument_ids)

        if error:
            return jsonify({'success': False, 'error': error}), 400

        return jsonify({
            'success': True,
            'message': f'Successfully removed {count} stock(s)',
            'count': count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@sector_management_bp.route('/api/subsectors/move-stocks', methods=['POST'])
@login_required
def api_move_stocks():
    """API endpoint to move stocks between sub-sectors"""
    try:
        data = request.get_json()
        from_subsector_id = data.get('from_subsector_id')
        to_subsector_id = data.get('to_subsector_id')
        instrument_ids = data.get('instrument_ids', [])

        if not all([from_subsector_id, to_subsector_id, instrument_ids]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400

        count, error = SubSectorService.move_stocks(
            from_subsector_id,
            to_subsector_id,
            instrument_ids
        )

        if error:
            return jsonify({'success': False, 'error': error}), 400

        return jsonify({
            'success': True,
            'message': f'Successfully moved {count} stock(s)',
            'count': count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@sector_management_bp.route('/api/unassigned-stocks')
@login_required
def api_get_unassigned_stocks():
    """API endpoint to get unassigned stocks"""
    try:
        sector_id = request.args.get('sector_id', type=int)
        search = request.args.get('search', type=str)
        limit = request.args.get('limit', 100, type=int)

        stocks = SubSectorService.get_unassigned_stocks(
            sector_id=sector_id,
            search=search,
            limit=limit
        )

        return jsonify({
            'success': True,
            'stocks': [{
                'id': s.id,
                'symbol': s.tradingsymbol,
                'name': s.name,
                'sector': s.sector
            } for s in stocks]
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@sector_management_bp.route('/api/subsectors/<int:subsector_id>/stocks')
@login_required
def api_get_subsector_stocks(subsector_id):
    """API endpoint to get stocks in a sub-sector"""
    try:
        search = request.args.get('search', type=str)

        subsector = SubSectorService.get_sub_sector_by_id(subsector_id)
        if not subsector:
            return jsonify({'success': False, 'error': 'Sub-sector not found'}), 404

        # Get all stocks (no pagination for API)
        query = subsector.instruments.filter_by(is_nifty500=True)

        if search:
            from sqlalchemy import or_
            query = query.filter(or_(
                Instrument.tradingsymbol.ilike(f'%{search}%'),
                Instrument.name.ilike(f'%{search}%')
            ))

        stocks = query.order_by(Instrument.tradingsymbol).all()

        return jsonify({
            'success': True,
            'stocks': [{
                'id': s.id,
                'symbol': s.tradingsymbol,
                'name': s.name,
                'sector': s.sector
            } for s in stocks]
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# REORDERING ROUTES
# ============================================================================

@sector_management_bp.route('/api/sectors/reorder', methods=['POST'])
@login_required
def api_reorder_sectors():
    """API endpoint to reorder sectors"""
    try:
        data = request.get_json()
        sector_ids = data.get('sector_ids', [])

        if not sector_ids:
            return jsonify({'success': False, 'error': 'No sectors provided'}), 400

        success, error = SectorService.reorder_sectors(sector_ids)

        if error:
            return jsonify({'success': False, 'error': error}), 400

        return jsonify({
            'success': True,
            'message': 'Sectors reordered successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@sector_management_bp.route('/api/subsectors/reorder', methods=['POST'])
@login_required
def api_reorder_subsectors():
    """API endpoint to reorder sub-sectors"""
    try:
        data = request.get_json()
        subsector_ids = data.get('subsector_ids', [])

        if not subsector_ids:
            return jsonify({'success': False, 'error': 'No sub-sectors provided'}), 400

        success, error = SubSectorService.reorder_subsectors(subsector_ids)

        if error:
            return jsonify({'success': False, 'error': error}), 400

        return jsonify({
            'success': True,
            'message': 'Sub-sectors reordered successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# SEARCH & UTILITY ROUTES
# ============================================================================

@sector_management_bp.route('/api/sectors/search')
@login_required
def api_search_sectors():
    """API endpoint to search sectors"""
    try:
        search_term = request.args.get('q', '', type=str)
        include_inactive = request.args.get('include_inactive', 'false') == 'true'

        if len(search_term) < 2:
            return jsonify({'success': True, 'sectors': []})

        sectors = SectorService.search_sectors(search_term, include_inactive)

        return jsonify({
            'success': True,
            'sectors': [s.to_dict() for s in sectors]
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@sector_management_bp.route('/api/sectors/<int:sector_id>/subsectors')
@login_required
def api_get_subsectors(sector_id):
    """API endpoint to get all sub-sectors for a sector"""
    try:
        include_inactive = request.args.get('include_inactive', 'false') == 'true'

        subsectors = SubSectorService.get_sub_sectors_by_sector(
            sector_id,
            include_inactive=include_inactive
        )

        return jsonify({
            'success': True,
            'subsectors': [s.to_dict() for s in subsectors]
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
