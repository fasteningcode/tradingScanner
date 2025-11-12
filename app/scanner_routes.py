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
from app.models import ScannerProfile, ScannerTask, ScanResult, ScanResultStock, Sector, SubSector, Instrument, HistoricalData
from app.forms import ScannerProfileForm
from app import scanner_service
from datetime import datetime
import json

scanner_bp = Blueprint('scanner', __name__, url_prefix='/scanner')


# ========================================
# Moving Average Calculation Helpers
# ========================================

def calculate_sma(candles, period):
    """
    Calculate Simple Moving Average (SMA) for given period

    Args:
        candles: List of candle dicts with 'close' prices (sorted oldest to newest)
        period: Number of periods (e.g., 9, 20, 50)

    Returns:
        float: SMA value or None if insufficient data
    """
    if not candles or len(candles) < period:
        return None

    # Take the last 'period' candles and calculate average of close prices
    recent_candles = candles[-period:]
    close_prices = [c.get('close') for c in recent_candles if c.get('close') is not None]

    if len(close_prices) < period:
        return None

    return sum(close_prices) / period


def calculate_ema(candles, period):
    """
    Calculate Exponential Moving Average (EMA) for given period

    Args:
        candles: List of candle dicts with 'close' prices (sorted oldest to newest)
        period: Number of periods (e.g., 9, 20, 50)

    Returns:
        float: EMA value or None if insufficient data
    """
    if not candles or len(candles) < period:
        return None

    close_prices = [c.get('close') for c in candles if c.get('close') is not None]

    if len(close_prices) < period:
        return None

    # Calculate multiplier: 2 / (period + 1)
    multiplier = 2 / (period + 1)

    # Start with SMA as the first EMA value
    ema = sum(close_prices[:period]) / period

    # Calculate EMA for remaining values
    for price in close_prices[period:]:
        ema = (price - ema) * multiplier + ema

    return ema


def get_stock_ma_values(stock, selected_sma, selected_ema, interval='day'):
    """
    Get MA values for a stock from its candlestick data

    Args:
        stock: Instrument object
        selected_sma: List of SMA periods (e.g., [9, 20, 50])
        selected_ema: List of EMA periods (e.g., [9, 20, 50])
        interval: Candlestick interval (default: 'day')

    Returns:
        dict: {
            'current_price': float,
            'sma': {9: value, 20: value, ...},
            'ema': {9: value, 20: value, ...},
            'has_data': bool,
            'error': str or None
        }
    """
    from app.models import HistoricalData

    result = {
        'current_price': None,
        'sma': {},
        'ema': {},
        'has_data': False,
        'error': None
    }

    # Get historical data for this stock
    hist_data = HistoricalData.query.filter_by(
        tradingsymbol=stock.tradingsymbol,
        interval=interval
    ).first()

    if not hist_data:
        result['error'] = 'No historical data'
        return result

    # Parse candlestick data
    candles = hist_data.get_candles()

    if not candles or len(candles) < 2:
        result['error'] = 'Insufficient candles'
        return result

    # Get current price (last close)
    result['current_price'] = candles[-1].get('close')

    if result['current_price'] is None:
        result['error'] = 'No current price'
        return result

    # Calculate SMAs
    for period in selected_sma:
        sma_value = calculate_sma(candles, period)
        if sma_value is not None:
            result['sma'][period] = sma_value

    # Calculate EMAs
    for period in selected_ema:
        ema_value = calculate_ema(candles, period)
        if ema_value is not None:
            result['ema'][period] = ema_value

    result['has_data'] = True
    return result


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


@scanner_bp.route('/results/<int:task_id>', methods=['GET'])
@login_required
def view_task_results(task_id):
    """View detailed results for a specific scan task"""
    try:
        # Get task and verify ownership
        task = ScannerTask.query.filter_by(id=task_id, user_id=current_user.id).first()
        if not task:
            flash('Scan task not found', 'error')
            return redirect(url_for('scanner.index', tab='results'))

        # Get task statistics
        total_results = ScanResultStock.query.filter_by(task_id=task_id).count()

        # Get profile info
        profile = task.profile
        criteria = {}
        if profile and profile.criteria:
            try:
                criteria = json.loads(profile.criteria)
            except json.JSONDecodeError:
                criteria = {}

        # Calculate scan duration
        duration_seconds = None
        if task.started_at and task.completed_at:
            duration = task.completed_at - task.started_at
            duration_seconds = int(duration.total_seconds())

        return render_template(
            'scanner/results_detail.html',
            task=task,
            profile=profile,
            criteria=criteria,
            total_results=total_results,
            duration_seconds=duration_seconds
        )

    except Exception as e:
        current_app.logger.error(f'Error viewing task results: {str(e)}', exc_info=True)
        flash('Error loading scan results', 'error')
        return redirect(url_for('scanner.index', tab='results'))


@scanner_bp.route('/api/results/<int:task_id>', methods=['GET'])
@login_required
def api_task_results(task_id):
    """API endpoint for scan results with pagination, search, and sorting"""
    try:
        # Get task and verify ownership
        task = ScannerTask.query.filter_by(id=task_id, user_id=current_user.id).first()
        if not task:
            return jsonify({
                'success': False,
                'error': 'Scan task not found'
            }), 404

        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 100)  # Max 100 per page

        # Get search parameter
        search = request.args.get('search', '').strip()

        # Get sort parameters
        sort_by = request.args.get('sort_by', 'scan_rank')
        order = request.args.get('order', 'asc')

        # Get matched_only filter (default True)
        matched_only = request.args.get('matched_only', 'true').lower() == 'true'

        # Build query
        query = ScanResultStock.query.filter_by(task_id=task_id)

        # Apply matched_only filter
        if matched_only and task.matched_stocks:
            # Only show stocks with rank <= matched_stocks count
            query = query.filter(ScanResultStock.scan_rank <= task.matched_stocks)

        # Apply search filter
        if search:
            query = query.filter(ScanResultStock.tradingsymbol.ilike(f'%{search}%'))

        # Apply sorting
        if sort_by == 'scan_rank':
            if order == 'desc':
                query = query.order_by(ScanResultStock.scan_rank.desc())
            else:
                query = query.order_by(ScanResultStock.scan_rank.asc())
        elif sort_by == 'tradingsymbol':
            if order == 'desc':
                query = query.order_by(ScanResultStock.tradingsymbol.desc())
            else:
                query = query.order_by(ScanResultStock.tradingsymbol.asc())
        elif sort_by == 'rs_vs_subsector':
            if order == 'desc':
                query = query.order_by(ScanResultStock.rs_vs_subsector.desc().nullslast())
            else:
                query = query.order_by(ScanResultStock.rs_vs_subsector.asc().nullslast())
        elif sort_by == 'rs_vs_sector':
            if order == 'desc':
                query = query.order_by(ScanResultStock.rs_vs_sector.desc().nullslast())
            else:
                query = query.order_by(ScanResultStock.rs_vs_sector.asc().nullslast())
        elif sort_by == 'stage':
            if order == 'desc':
                query = query.order_by(ScanResultStock.stage.desc())
            else:
                query = query.order_by(ScanResultStock.stage.asc())
        elif sort_by == 'scan_score':
            if order == 'desc':
                query = query.order_by(ScanResultStock.scan_score.desc())
            else:
                query = query.order_by(ScanResultStock.scan_score.asc())

        # Paginate
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # Convert results to dict
        results = [result.to_dict() for result in pagination.items]

        # Get instrument names
        for result in results:
            instrument = Instrument.query.filter_by(tradingsymbol=result['tradingsymbol']).first()
            if instrument:
                result['name'] = instrument.name

        return jsonify({
            'success': True,
            'task': {
                'id': task.id,
                'status': task.status,
                'profile_name': task.profile.name if task.profile else 'Unknown',
                'total_stocks': task.total_stocks,
                'matched_stocks': task.matched_stocks,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None
            },
            'results': results,
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
        current_app.logger.error(f'Error getting task results API: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scanner_bp.route('/results/<int:task_id>/debug', methods=['GET'])
@login_required
def debug_task_results(task_id):
    """Debug view showing step-by-step filter breakdown for a scan"""
    try:
        # Get task and verify ownership
        task = ScannerTask.query.filter_by(id=task_id, user_id=current_user.id).first()
        if not task:
            flash('Scan task not found', 'error')
            return redirect(url_for('scanner.index', tab='results'))

        # Get profile criteria - use snapshot if available, otherwise use current profile
        profile = task.profile
        criteria = {}
        criteria_source = "current"  # Track whether we're using snapshot or current

        if task.criteria_snapshot:
            # Use the criteria snapshot from when the scan was run
            try:
                criteria = json.loads(task.criteria_snapshot)
                criteria_source = "snapshot"
            except json.JSONDecodeError:
                # Fallback to current profile criteria
                if profile and profile.criteria:
                    try:
                        criteria = json.loads(profile.criteria)
                    except json.JSONDecodeError:
                        criteria = {}
        elif profile and profile.criteria:
            # No snapshot available, use current profile criteria
            try:
                criteria = json.loads(profile.criteria)
            except json.JSONDecodeError:
                criteria = {}

        # Re-run filters with debug enabled to get step-by-step breakdown
        # This simulates what happened during the scan
        debug_info = {
            'task_id': task_id,
            'profile_name': profile.name if profile else 'Unknown',
            'total_stocks_initial': 502,  # NIFTY 500 + some
            'filters_applied': [],
            'criteria_source': criteria_source  # Pass this to template for warning
        }

        # Initial count
        initial_query = Instrument.query.filter_by(
            exchange='NSE',
            instrument_type='EQ',
            is_nifty500=True
        )
        initial_count = initial_query.count()
        debug_info['total_stocks_initial'] = initial_count

        # Apply each filter and track results
        query = initial_query

        # Stage/Sector/Subsector filter
        enable_scan_level_filter = criteria.get('enable_scan_level_filter', True)
        if enable_scan_level_filter:
            scan_level = criteria.get('scan_level', 'subsector')
            selected_ids = []
            if scan_level == 'stage':
                selected_ids = criteria.get('selected_stages', [])
            elif scan_level == 'sector':
                selected_ids = criteria.get('selected_sectors', [])
            elif scan_level == 'subsector':
                selected_ids = criteria.get('selected_subsectors', [])

            # Actually apply the filter and count results
            if selected_ids:
                if scan_level == 'stage':
                    # For stage level, need to check stock, subsector AND sector alignment
                    from app.models import Sector
                    query = query.join(SubSector, Instrument.sub_sector_id == SubSector.id).join(
                        Sector, SubSector.sector_id == Sector.id
                    ).filter(
                        Instrument.current_stage.in_(selected_ids),
                        SubSector.current_stage.in_(selected_ids),
                        Sector.current_stage.in_(selected_ids)
                    )
                elif scan_level == 'sector':
                    query = query.join(SubSector, Instrument.sub_sector_id == SubSector.id).filter(
                        SubSector.sector_id.in_(selected_ids)
                    )
                    # Apply stock stage filter (default to stages 1,2 if not selected)
                    stock_stages = criteria.get('selected_stages', [1, 2])
                    query = query.filter(Instrument.current_stage.in_(stock_stages))
                elif scan_level == 'subsector':
                    query = query.filter(Instrument.sub_sector_id.in_(selected_ids))

                after_count = query.count()
                debug_info['filters_applied'].append({
                    'name': f'{scan_level.title()} Level Filter',
                    'enabled': True,
                    'criteria': f'Selected: {len(selected_ids)} {scan_level}(s)',
                    'passed': after_count,
                    'failed': initial_count - after_count
                })

        # RS Filter
        enable_rs_filter = criteria.get('enable_rs_filter', False)
        if enable_rs_filter:
            rs_criteria = []
            if criteria.get('rs_sub_min'):
                rs_criteria.append(f"RS Sub >= {criteria['rs_sub_min']}")
            if criteria.get('rs_sub_max'):
                rs_criteria.append(f"RS Sub <= {criteria['rs_sub_max']}")
            if criteria.get('rs_sec_min'):
                rs_criteria.append(f"RS Sec >= {criteria['rs_sec_min']}")
            if criteria.get('rs_sec_max'):
                rs_criteria.append(f"RS Sec <= {criteria['rs_sec_max']}")

            debug_info['filters_applied'].append({
                'name': 'Relative Strength Filter',
                'enabled': True,
                'criteria': ', '.join(rs_criteria) if rs_criteria else 'No RS criteria',
                'passed': task.total_stocks,
                'failed': 0
            })

        # Volume Filter
        enable_volume_filter = criteria.get('enable_volume_contraction_filter', False)
        if enable_volume_filter:
            vol_status = criteria.get('selected_volume_status', [])
            vol_classification = criteria.get('selected_volume_classification', [])
            debug_info['filters_applied'].append({
                'name': 'Volume Contraction Filter',
                'enabled': True,
                'criteria': f"Status: {vol_status}, Classification: {vol_classification}",
                'passed': task.total_stocks,
                'failed': 0
            })

        # MA Filter
        enable_ma_filter = criteria.get('enable_ma_filter', False)
        if enable_ma_filter:
            sma = criteria.get('selected_sma', [])
            ema = criteria.get('selected_ema', [])

            # Count stocks before MA filter (current query count)
            before_ma_count = query.count()

            # MA filter is applied in _get_stocks_to_scan() by checking historical data
            # We can't easily replicate that in SQL, so use task.total_stocks as after count
            after_ma_count = task.total_stocks

            debug_info['filters_applied'].append({
                'name': 'Moving Average Filter',
                'enabled': True,
                'criteria': f"SMA: {sma}, EMA: {ema}",
                'passed': after_ma_count,
                'failed': before_ma_count - after_ma_count
            })

            # Update query to reflect MA filtering (though we can't actually query it)
            # The actual filtering happens in scanner_service by checking candlestick data

        # Price Action Filter
        enable_price_action = criteria.get('enable_price_action_filter', False)
        if enable_price_action:
            strategies = criteria.get('selected_price_action_strategies', [])
            lookback = criteria.get('price_action_lookback_days', 252)
            debug_info['filters_applied'].append({
                'name': 'Price Action Filter',
                'enabled': True,
                'criteria': f"Patterns: {strategies}, Lookback: {lookback} days",
                'passed': task.matched_stocks,
                'failed': task.total_stocks - task.matched_stocks
            })

        debug_info['final_matched'] = task.matched_stocks

        return render_template(
            'scanner/results_debug.html',
            task=task,
            profile=profile,
            debug_info=debug_info
        )

    except Exception as e:
        current_app.logger.error(f'Error debugging task results: {str(e)}', exc_info=True)
        flash('Error loading debug information', 'error')
        return redirect(url_for('scanner.view_task_results', task_id=task_id))


@scanner_bp.route('/debug-filter', methods=['POST'])
@login_required
def debug_filter():
    """
    Debug a single filter by running it and returning detailed step-by-step logs
    """
    try:
        data = request.get_json() or {}
        filter_type = data.get('filter_type')
        criteria = data.get('criteria', {})

        if not filter_type:
            return jsonify({
                'success': False,
                'error': 'Filter type is required'
            }), 400

        current_app.logger.info(f'Debug run for filter: {filter_type}, criteria: {criteria}')

        # Import here to avoid circular imports
        from app.models import Sector

        # Initialize debug info structure
        debug_info = {
            'total_stocks': 0,
            'matched_stocks': 0,
            'eliminated_stocks': 0,
            'steps': [],
            'sample_stocks': [],
            'logs': []
        }

        # Start with all NIFTY 500 stocks
        query = Instrument.query.filter_by(
            exchange='NSE',
            instrument_type='EQ',
            is_nifty500=True
        )

        initial_count = query.count()
        debug_info['total_stocks'] = initial_count
        debug_info['logs'].append(f'[INIT] Starting with {initial_count} NIFTY 500 stocks')

        # Apply the selected filter
        if filter_type == 'stage_level':
            query, filter_debug = _apply_stage_level_filter_debug(query, criteria)
            debug_info['steps'].extend(filter_debug['steps'])
            debug_info['logs'].extend(filter_debug['logs'])

        elif filter_type == 'rs':
            query, filter_debug = _apply_rs_filter_debug(query, criteria)
            debug_info['steps'].extend(filter_debug['steps'])
            debug_info['logs'].extend(filter_debug['logs'])

        elif filter_type == 'ma':
            query, filter_debug = _apply_ma_filter_debug(query, criteria)
            debug_info['steps'].extend(filter_debug['steps'])
            debug_info['logs'].extend(filter_debug['logs'])

        elif filter_type == 'volume':
            query, filter_debug = _apply_volume_filter_debug(query, criteria)
            debug_info['steps'].extend(filter_debug['steps'])
            debug_info['logs'].extend(filter_debug['logs'])

        elif filter_type == 'price_action':
            query, filter_debug = _apply_price_action_filter_debug(query, criteria)
            debug_info['steps'].extend(filter_debug['steps'])
            debug_info['logs'].extend(filter_debug['logs'])

        else:
            return jsonify({
                'success': False,
                'error': f'Unknown filter type: {filter_type}'
            }), 400

        # Get final results
        matched_stocks = query.all()
        debug_info['matched_stocks'] = len(matched_stocks)
        debug_info['eliminated_stocks'] = initial_count - len(matched_stocks)
        debug_info['logs'].append(f'[RESULT] Matched: {len(matched_stocks)}, Eliminated: {debug_info["eliminated_stocks"]}')

        # Get all matched stocks (full list for frontend pagination)
        for stock in matched_stocks:
            debug_info['sample_stocks'].append({
                'tradingsymbol': stock.tradingsymbol,
                'name': stock.name,
                'sector': stock.sub_sector_obj.sector.name if stock.sub_sector_obj and stock.sub_sector_obj.sector else '',
                'subsector': stock.sub_sector_obj.name if stock.sub_sector_obj else '',
                'current_stage': stock.current_stage,
                'rs_vs_subsector': round(stock.rs_vs_subsector, 2) if stock.rs_vs_subsector else None,
                'rs_vs_sector': round(stock.rs_vs_sector, 2) if stock.rs_vs_sector else None,
                'volume_dryup_status': stock.volume_dryup_status,
                'volume_dryup_classification': stock.volume_dryup_classification,
                'volume_ratio_pct': round(stock.volume_ratio_pct, 2) if stock.volume_ratio_pct else None
            })

        return jsonify({
            'success': True,
            'debug_info': debug_info
        })

    except Exception as e:
        current_app.logger.error(f'Error in debug filter: {str(e)}', exc_info=True)
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


# Debug Filter Helper Functions

def _apply_stage_level_filter_debug(query, criteria):
    """Apply stage level filter with detailed debugging"""
    debug = {'steps': [], 'logs': []}

    scan_level = criteria.get('scan_level', 'subsector')
    selected_stages = criteria.get('selected_stages', [])
    selected_sectors = criteria.get('selected_sectors', [])
    selected_subsectors = criteria.get('selected_subsectors', [])

    debug['logs'].append(f'[STAGE_LEVEL] Scan level: {scan_level}')

    if scan_level == 'stage' and selected_stages:
        debug['logs'].append(f'[STAGE_LEVEL] Filtering by stages: {selected_stages}')
        debug['logs'].append(f'[STAGE_LEVEL] Criteria: Stock stage, Subsector stage, AND Sector stage must ALL be in {selected_stages}')

        from app.models import Sector

        # Get all stocks before filtering to show detailed rejection reasons
        all_stocks_query = query.join(SubSector, Instrument.sub_sector_id == SubSector.id).join(
            Sector, SubSector.sector_id == Sector.id
        )
        all_stocks = all_stocks_query.all()

        debug['logs'].append(f'[STAGE_LEVEL] Analyzing {len(all_stocks)} stocks...')
        debug['logs'].append('')

        # Track statistics
        accepted_count = 0
        rejected_stock_stage = 0
        rejected_subsector_stage = 0
        rejected_sector_stage = 0
        rejected_multiple = 0

        # Analyze each stock
        for stock in all_stocks:
            stock_stage = stock.current_stage
            subsector_stage = stock.sub_sector_obj.current_stage if stock.sub_sector_obj else None
            sector_stage = stock.sub_sector_obj.sector.current_stage if stock.sub_sector_obj and stock.sub_sector_obj.sector else None

            stock_match = stock_stage in selected_stages
            subsector_match = subsector_stage in selected_stages
            sector_match = sector_stage in selected_stages

            if stock_match and subsector_match and sector_match:
                # ACCEPTED
                accepted_count += 1
                debug['logs'].append(
                    f'✓ ACCEPTED: {stock.tradingsymbol} | '
                    f'Stock Stage={stock_stage}, '
                    f'Subsector Stage={subsector_stage} ({stock.sub_sector_obj.name if stock.sub_sector_obj else "N/A"}), '
                    f'Sector Stage={sector_stage} ({stock.sub_sector_obj.sector.name if stock.sub_sector_obj and stock.sub_sector_obj.sector else "N/A"})'
                )
            else:
                # REJECTED - determine why
                rejection_reasons = []
                failures = 0

                if not stock_match:
                    rejection_reasons.append(f'Stock stage {stock_stage} not in {selected_stages}')
                    rejected_stock_stage += 1
                    failures += 1

                if not subsector_match:
                    rejection_reasons.append(f'Subsector stage {subsector_stage} not in {selected_stages}')
                    rejected_subsector_stage += 1
                    failures += 1

                if not sector_match:
                    rejection_reasons.append(f'Sector stage {sector_stage} not in {selected_stages}')
                    rejected_sector_stage += 1
                    failures += 1

                if failures > 1:
                    rejected_multiple += 1

                debug['logs'].append(
                    f'✗ REJECTED: {stock.tradingsymbol} | '
                    f'Stock Stage={stock_stage}, '
                    f'Subsector Stage={subsector_stage} ({stock.sub_sector_obj.name if stock.sub_sector_obj else "N/A"}), '
                    f'Sector Stage={sector_stage} ({stock.sub_sector_obj.sector.name if stock.sub_sector_obj and stock.sub_sector_obj.sector else "N/A"}) | '
                    f'Reason: {"; ".join(rejection_reasons)}'
                )

        debug['logs'].append('')
        debug['logs'].append(f'[STAGE_LEVEL] === FILTERING SUMMARY ===')
        debug['logs'].append(f'[STAGE_LEVEL] Total stocks analyzed: {len(all_stocks)}')
        debug['logs'].append(f'[STAGE_LEVEL] Accepted: {accepted_count}')
        debug['logs'].append(f'[STAGE_LEVEL] Rejected: {len(all_stocks) - accepted_count}')
        debug['logs'].append(f'[STAGE_LEVEL] Rejection breakdown:')
        debug['logs'].append(f'[STAGE_LEVEL]   - Stock stage mismatch: {rejected_stock_stage}')
        debug['logs'].append(f'[STAGE_LEVEL]   - Subsector stage mismatch: {rejected_subsector_stage}')
        debug['logs'].append(f'[STAGE_LEVEL]   - Sector stage mismatch: {rejected_sector_stage}')
        debug['logs'].append(f'[STAGE_LEVEL]   - Multiple mismatches: {rejected_multiple}')

        # Apply the actual filter to the query
        query = query.join(SubSector, Instrument.sub_sector_id == SubSector.id).join(
            Sector, SubSector.sector_id == Sector.id
        ).filter(
            Instrument.current_stage.in_(selected_stages),
            SubSector.current_stage.in_(selected_stages),
            Sector.current_stage.in_(selected_stages)
        )

        count = query.count()
        debug['steps'].append({
            'description': 'Filter by Weinstein Stages',
            'details': f'Stocks in stages {selected_stages} (stock, subsector, AND sector must ALL match)',
            'criteria': f'Stages: {", ".join(map(str, selected_stages))}',
            'count': count,
            'passed': count > 0
        })

    elif scan_level == 'sector' and selected_sectors:
        from app.models import Sector

        # Get sector names for logging
        sectors = Sector.query.filter(Sector.id.in_(selected_sectors)).all()
        sector_names = [s.name for s in sectors]

        debug['logs'].append(f'[SECTOR_LEVEL] Filtering by sectors: {sector_names}')
        debug['logs'].append(f'[SECTOR_LEVEL] Sector IDs: {selected_sectors}')

        # First, get all stocks from selected sectors
        all_stocks_query = query.join(SubSector, Instrument.sub_sector_id == SubSector.id).filter(
            SubSector.sector_id.in_(selected_sectors)
        )
        all_stocks = all_stocks_query.all()

        debug['logs'].append(f'[SECTOR_LEVEL] Found {len(all_stocks)} stocks in selected sectors')
        debug['logs'].append('')

        # For sector-level scan, ALWAYS filter by stages
        # If no stages selected, default to stages 1 and 2 (Accumulation and Markup)
        selected_stages = criteria.get('selected_stages', [])
        if not selected_stages:
            selected_stages = [1, 2]  # Default to Accumulation and Markup stages
            debug['logs'].append(f'[SECTOR_LEVEL] No stages selected - defaulting to stages {selected_stages} (Accumulation and Markup)')

        debug['logs'].append('')
        debug['logs'].append(f'[SECTOR_LEVEL] ======================================')
        debug['logs'].append(f'[SECTOR_LEVEL] STAGE FILTERING (ALWAYS ENABLED FOR SECTOR SCAN)')
        debug['logs'].append(f'[SECTOR_LEVEL] Filtering by stock stages: {selected_stages}')
        debug['logs'].append(f'[SECTOR_LEVEL] ======================================')
        debug['logs'].append('')

        if True:  # Always filter by stages in sector-level scan
            debug['logs'].append(f'[SECTOR_LEVEL] ✓ Stage filtering ENABLED - will filter by stock stages: {selected_stages}')
            debug['logs'].append(f'[SECTOR_LEVEL] Analyzing {len(all_stocks)} stocks...')
            debug['logs'].append('')

            # Track statistics
            accepted_count = 0
            rejected_count = 0
            stocks_by_sector = {}

            # Analyze each stock
            for stock in all_stocks:
                stock_stage = stock.current_stage
                sector_name = stock.sub_sector_obj.sector.name if stock.sub_sector_obj and stock.sub_sector_obj.sector else 'N/A'
                subsector_name = stock.sub_sector_obj.name if stock.sub_sector_obj else 'N/A'

                if sector_name not in stocks_by_sector:
                    stocks_by_sector[sector_name] = {'accepted': 0, 'rejected': 0}

                if stock_stage in selected_stages:
                    # ACCEPTED
                    accepted_count += 1
                    stocks_by_sector[sector_name]['accepted'] += 1
                    debug['logs'].append(
                        f'✓ ACCEPTED: {stock.tradingsymbol} | '
                        f'Sector={sector_name}, Subsector={subsector_name}, Stock Stage={stock_stage}'
                    )
                else:
                    # REJECTED
                    rejected_count += 1
                    stocks_by_sector[sector_name]['rejected'] += 1
                    debug['logs'].append(
                        f'✗ REJECTED: {stock.tradingsymbol} | '
                        f'Sector={sector_name}, Subsector={subsector_name}, Stock Stage={stock_stage} | '
                        f'Reason: Stock stage {stock_stage} not in {selected_stages}'
                    )

            debug['logs'].append('')
            debug['logs'].append(f'[SECTOR_LEVEL] === FILTERING SUMMARY ===')
            debug['logs'].append(f'[SECTOR_LEVEL] Total stocks in selected sectors: {len(all_stocks)}')
            debug['logs'].append(f'[SECTOR_LEVEL] Accepted (matching stage): {accepted_count}')
            debug['logs'].append(f'[SECTOR_LEVEL] Rejected (wrong stage): {rejected_count}')
            debug['logs'].append(f'[SECTOR_LEVEL] Breakdown by sector:')
            for sector_name, counts in stocks_by_sector.items():
                debug['logs'].append(f'[SECTOR_LEVEL]   {sector_name}: {counts["accepted"]} accepted, {counts["rejected"]} rejected')

            # Apply the filter
            query = all_stocks_query.filter(Instrument.current_stage.in_(selected_stages))
            count = query.count()

        debug['steps'].append({
            'description': 'Filter by Selected Sectors' + (f' and Stages {selected_stages}' if selected_stages else ''),
            'details': f'{len(selected_sectors)} sectors selected: {", ".join(sector_names)}' + (f'. Stock stages: {selected_stages}' if selected_stages else ''),
            'criteria': f'Sectors: {", ".join(sector_names)}' + (f', Stages: {", ".join(map(str, selected_stages))}' if selected_stages else ''),
            'count': count,
            'passed': count > 0
        })

    elif scan_level == 'subsector' and selected_subsectors:
        # Get subsector names for logging
        subsectors = SubSector.query.filter(SubSector.id.in_(selected_subsectors)).all()
        subsector_names = [f"{ss.name} ({ss.sector.name if ss.sector else 'N/A'})" for ss in subsectors]

        debug['logs'].append(f'[SUBSECTOR_LEVEL] Filtering by subsectors: {subsector_names}')
        debug['logs'].append(f'[SUBSECTOR_LEVEL] Subsector IDs: {selected_subsectors}')

        # First, get all stocks from selected subsectors
        all_stocks_query = query.filter(
            Instrument.sub_sector_id.in_(selected_subsectors)
        )
        all_stocks = all_stocks_query.all()

        debug['logs'].append(f'[SUBSECTOR_LEVEL] Found {len(all_stocks)} stocks in selected subsectors')
        debug['logs'].append('')

        # For subsector-level scan, ALWAYS filter by stages
        # If no stages selected, default to stages 1 and 2 (Accumulation and Markup)
        selected_stages = criteria.get('selected_stages', [])
        if not selected_stages:
            selected_stages = [1, 2]  # Default to Accumulation and Markup stages
            debug['logs'].append(f'[SUBSECTOR_LEVEL] No stages selected - defaulting to stages {selected_stages} (Accumulation and Markup)')

        debug['logs'].append('')
        debug['logs'].append(f'[SUBSECTOR_LEVEL] ======================================')
        debug['logs'].append(f'[SUBSECTOR_LEVEL] STAGE FILTERING (ALWAYS ENABLED FOR SUBSECTOR SCAN)')
        debug['logs'].append(f'[SUBSECTOR_LEVEL] Filtering by stock stages: {selected_stages}')
        debug['logs'].append(f'[SUBSECTOR_LEVEL] ======================================')
        debug['logs'].append('')

        if True:  # Always filter by stages in subsector-level scan
            debug['logs'].append(f'[SUBSECTOR_LEVEL] ✓ Stage filtering ENABLED - will filter by stock stages: {selected_stages}')
            debug['logs'].append(f'[SUBSECTOR_LEVEL] Analyzing {len(all_stocks)} stocks...')
            debug['logs'].append('')

            # Track statistics
            accepted_count = 0
            rejected_count = 0
            stocks_by_subsector = {}

            # Analyze each stock
            for stock in all_stocks:
                stock_stage = stock.current_stage
                sector_name = stock.sub_sector_obj.sector.name if stock.sub_sector_obj and stock.sub_sector_obj.sector else 'N/A'
                subsector_name = stock.sub_sector_obj.name if stock.sub_sector_obj else 'N/A'

                if subsector_name not in stocks_by_subsector:
                    stocks_by_subsector[subsector_name] = {'accepted': 0, 'rejected': 0}

                if stock_stage in selected_stages:
                    # ACCEPTED
                    accepted_count += 1
                    stocks_by_subsector[subsector_name]['accepted'] += 1
                    debug['logs'].append(
                        f'✓ ACCEPTED: {stock.tradingsymbol} | '
                        f'Sector={sector_name}, Subsector={subsector_name}, Stock Stage={stock_stage}'
                    )
                else:
                    # REJECTED
                    rejected_count += 1
                    stocks_by_subsector[subsector_name]['rejected'] += 1
                    debug['logs'].append(
                        f'✗ REJECTED: {stock.tradingsymbol} | '
                        f'Sector={sector_name}, Subsector={subsector_name}, Stock Stage={stock_stage} | '
                        f'Reason: Stock stage {stock_stage} not in {selected_stages}'
                    )

            debug['logs'].append('')
            debug['logs'].append(f'[SUBSECTOR_LEVEL] === FILTERING SUMMARY ===')
            debug['logs'].append(f'[SUBSECTOR_LEVEL] Total stocks in selected subsectors: {len(all_stocks)}')
            debug['logs'].append(f'[SUBSECTOR_LEVEL] Accepted (matching stage): {accepted_count}')
            debug['logs'].append(f'[SUBSECTOR_LEVEL] Rejected (wrong stage): {rejected_count}')
            debug['logs'].append(f'[SUBSECTOR_LEVEL] Breakdown by subsector:')
            for subsector_name, counts in stocks_by_subsector.items():
                debug['logs'].append(f'[SUBSECTOR_LEVEL]   {subsector_name}: {counts["accepted"]} accepted, {counts["rejected"]} rejected')

            # Apply the filter
            query = all_stocks_query.filter(Instrument.current_stage.in_(selected_stages))
            count = query.count()

        debug['steps'].append({
            'description': 'Filter by Selected Subsectors' + (f' and Stages {selected_stages}' if selected_stages else ''),
            'details': f'{len(selected_subsectors)} subsectors selected' + (f'. Stock stages: {selected_stages}' if selected_stages else ''),
            'criteria': f'Subsectors: {len(selected_subsectors)} selected' + (f', Stages: {", ".join(map(str, selected_stages))}' if selected_stages else ''),
            'count': count,
            'passed': count > 0
        })

    else:
        debug['logs'].append(f'[STAGE_LEVEL] No filter applied - scanning all stocks')
        count = query.count()
        debug['steps'].append({
            'description': 'No Stage Level Filter Applied',
            'details': 'Scanning all NIFTY 500 stocks',
            'count': count,
            'passed': True
        })

    return query, debug


def _apply_rs_filter_debug(query, criteria):
    """Apply RS filter with detailed debugging"""
    debug = {'steps': [], 'logs': []}

    rs_sub_min = criteria.get('rs_sub_min')
    rs_sub_max = criteria.get('rs_sub_max')
    rs_sec_min = criteria.get('rs_sec_min')
    rs_sec_max = criteria.get('rs_sec_max')

    debug['logs'].append(f'[RS_FILTER] RS Sub range: [{rs_sub_min}, {rs_sub_max}]')
    debug['logs'].append(f'[RS_FILTER] RS Sec range: [{rs_sec_min}, {rs_sec_max}]')

    initial_count = query.count()

    # Get initial RS statistics
    total_stocks = query.count()
    stocks_with_rs_sub = query.filter(Instrument.rs_vs_subsector.isnot(None)).count()
    stocks_with_rs_sec = query.filter(Instrument.rs_vs_sector.isnot(None)).count()
    stocks_without_sector = query.filter(Instrument.sector.is_(None) | (Instrument.sector == '')).count()

    debug['logs'].append(f'[RS_STATS] Total stocks in query: {total_stocks}')
    debug['logs'].append(f'[RS_STATS] Stocks with RS vs SubSector: {stocks_with_rs_sub} ({100*stocks_with_rs_sub//total_stocks if total_stocks > 0 else 0}%)')
    debug['logs'].append(f'[RS_STATS] Stocks with RS vs Sector: {stocks_with_rs_sec} ({100*stocks_with_rs_sec//total_stocks if total_stocks > 0 else 0}%)')
    debug['logs'].append(f'[RS_STATS] Stocks without sector assignment: {stocks_without_sector}')

    # Show sample stocks with RS values
    sample_with_rs = query.filter(Instrument.rs_vs_subsector.isnot(None)).order_by(Instrument.rs_vs_subsector.desc()).limit(5).all()
    if sample_with_rs:
        debug['logs'].append('[RS_SAMPLES] Top 5 stocks by RS vs SubSector:')
        for stock in sample_with_rs:
            debug['logs'].append(f'  - {stock.tradingsymbol}: RS_Sub={stock.rs_vs_subsector:.2f}, RS_Sec={stock.rs_vs_sector:.2f}, Sector={stock.sector or "None"}, SubSector={stock.sub_sector or "None"}')

    # Show sample stocks without RS values
    sample_without_rs = query.filter(Instrument.rs_vs_subsector.is_(None)).limit(5).all()
    if sample_without_rs:
        debug['logs'].append('[RS_MISSING] Sample stocks WITHOUT RS values:')
        for stock in sample_without_rs:
            debug['logs'].append(f'  - {stock.tradingsymbol}: Sector={stock.sector or "MISSING"}, SubSector={stock.sub_sector or "MISSING"}')
            if not stock.sector or stock.sector == '':
                debug['logs'].append(f'    → Cannot calculate RS without sector assignment')

    # Apply RS vs Subsector filters
    if rs_sub_min is not None:
        before_filter = query.count()
        query = query.filter(Instrument.rs_vs_subsector.isnot(None))
        query = query.filter(Instrument.rs_vs_subsector >= rs_sub_min)
        count = query.count()
        eliminated = before_filter - count
        debug['logs'].append(f'[RS_FILTER] After RS Sub Min >= {rs_sub_min}: {count} stocks (eliminated {eliminated})')

        # Show sample eliminated stocks
        if eliminated > 0:
            eliminated_stocks = Instrument.query.filter(
                Instrument.id.in_([s.id for s in query.all()[:5]])
            ).filter(
                (Instrument.rs_vs_subsector < rs_sub_min) | Instrument.rs_vs_subsector.is_(None)
            ).limit(3).all()
            if eliminated_stocks:
                debug['logs'].append(f'[RS_ELIMINATED] Sample stocks below RS_Sub {rs_sub_min}:')
                for stock in eliminated_stocks:
                    rs_val = stock.rs_vs_subsector if stock.rs_vs_subsector is not None else 'NULL'
                    debug['logs'].append(f'  - {stock.tradingsymbol}: RS_Sub={rs_val}')

        debug['steps'].append({
            'description': f'RS vs Subsector >= {rs_sub_min}',
            'details': f'Eliminated {eliminated} stocks below minimum threshold',
            'criteria': f'Minimum RS vs Subsector: {rs_sub_min}',
            'count': count,
            'passed': count > 0
        })
        initial_count = count

    if rs_sub_max is not None:
        before_filter = query.count()
        query = query.filter(Instrument.rs_vs_subsector.isnot(None))
        query = query.filter(Instrument.rs_vs_subsector <= rs_sub_max)
        count = query.count()
        eliminated = before_filter - count
        debug['logs'].append(f'[RS_FILTER] After RS Sub Max <= {rs_sub_max}: {count} stocks (eliminated {eliminated})')
        debug['steps'].append({
            'description': f'RS vs Subsector <= {rs_sub_max}',
            'details': f'Eliminated {eliminated} stocks above maximum threshold',
            'criteria': f'Maximum RS vs Subsector: {rs_sub_max}',
            'count': count,
            'passed': count > 0
        })
        initial_count = count

    # Apply RS vs Sector filters
    if rs_sec_min is not None:
        before_filter = query.count()
        query = query.filter(Instrument.rs_vs_sector.isnot(None))
        query = query.filter(Instrument.rs_vs_sector >= rs_sec_min)
        count = query.count()
        eliminated = before_filter - count
        debug['logs'].append(f'[RS_FILTER] After RS Sec Min >= {rs_sec_min}: {count} stocks (eliminated {eliminated})')
        debug['steps'].append({
            'description': f'RS vs Sector >= {rs_sec_min}',
            'details': f'Eliminated {eliminated} stocks below minimum threshold',
            'criteria': f'Minimum RS vs Sector: {rs_sec_min}',
            'count': count,
            'passed': count > 0
        })
        initial_count = count

    if rs_sec_max is not None:
        before_filter = query.count()
        query = query.filter(Instrument.rs_vs_sector.isnot(None))
        query = query.filter(Instrument.rs_vs_sector <= rs_sec_max)
        count = query.count()
        eliminated = before_filter - count
        debug['logs'].append(f'[RS_FILTER] After RS Sec Max <= {rs_sec_max}: {count} stocks (eliminated {eliminated})')
        debug['steps'].append({
            'description': f'RS vs Sector <= {rs_sec_max}',
            'details': f'Eliminated {eliminated} stocks above maximum threshold',
            'criteria': f'Maximum RS vs Sector: {rs_sec_max}',
            'count': count,
            'passed': count > 0
        })

    if not rs_sub_min and not rs_sub_max and not rs_sec_min and not rs_sec_max:
        debug['logs'].append(f'[RS_FILTER] No RS filter applied (all ranges set to [-100, 100])')
        count = query.count()
        debug['steps'].append({
            'description': 'No RS Filter Applied',
            'details': 'All RS criteria set to full range [-100, 100]',
            'count': count,
            'passed': True
        })

    # Final RS distribution of matched stocks
    final_stocks = query.limit(100).all()
    if final_stocks:
        rs_sub_values = [s.rs_vs_subsector for s in final_stocks if s.rs_vs_subsector is not None]
        rs_sec_values = [s.rs_vs_sector for s in final_stocks if s.rs_vs_sector is not None]
        if rs_sub_values:
            debug['logs'].append(f'[RS_DISTRIBUTION] Matched stocks RS vs SubSector: Min={min(rs_sub_values):.2f}, Max={max(rs_sub_values):.2f}, Avg={sum(rs_sub_values)/len(rs_sub_values):.2f}')
        if rs_sec_values:
            debug['logs'].append(f'[RS_DISTRIBUTION] Matched stocks RS vs Sector: Min={min(rs_sec_values):.2f}, Max={max(rs_sec_values):.2f}, Avg={sum(rs_sec_values)/len(rs_sec_values):.2f}')

    return query, debug


def _apply_ma_filter_debug(query, criteria):
    """Apply MA filter with detailed debugging - Price must be ABOVE all selected MAs"""
    debug = {'steps': [], 'logs': []}

    selected_sma = criteria.get('selected_sma', [])
    selected_ema = criteria.get('selected_ema', [])

    debug['logs'].append(f'[MA_FILTER] Selected SMA: {selected_sma}')
    debug['logs'].append(f'[MA_FILTER] Selected EMA: {selected_ema}')

    if not selected_sma and not selected_ema:
        debug['logs'].append(f'[MA_FILTER] No MA filter applied')
        count = query.count()
        debug['steps'].append({
            'description': 'No Moving Average Filter Applied',
            'details': 'No moving averages selected',
            'count': count,
            'passed': True
        })
        return query, debug

    # MA filtering - check each stock individually
    initial_count = query.count()
    all_stocks = query.all()

    debug['logs'].append(f'[MA_FILTER] Analyzing {initial_count} stocks for MA criteria')
    debug['logs'].append(f'[MA_FILTER] Criteria: Price must be ABOVE all selected MAs')
    debug['logs'].append('')

    passed_stocks = []
    rejected_stocks = []

    for stock in all_stocks:
        # Get MA values for this stock
        ma_data = get_stock_ma_values(stock, selected_sma, selected_ema, interval='day')

        # Check if we have data
        if not ma_data['has_data'] or ma_data['error']:
            rejected_stocks.append(stock.id)
            debug['logs'].append(f'✗ {stock.tradingsymbol}: {ma_data["error"]}')
            continue

        current_price = ma_data['current_price']

        # Check if price is above ALL selected MAs
        price_above_all = True
        ma_details = []

        # Check SMAs
        for period in selected_sma:
            if period in ma_data['sma']:
                sma_val = ma_data['sma'][period]
                is_above = current_price > sma_val
                symbol = '✓' if is_above else '✗'
                ma_details.append(f'SMA{period}={sma_val:.2f} {symbol}')
                if not is_above:
                    price_above_all = False
            else:
                ma_details.append(f'SMA{period}=N/A ✗')
                price_above_all = False

        # Check EMAs
        for period in selected_ema:
            if period in ma_data['ema']:
                ema_val = ma_data['ema'][period]
                is_above = current_price > ema_val
                symbol = '✓' if is_above else '✗'
                ma_details.append(f'EMA{period}={ema_val:.2f} {symbol}')
                if not is_above:
                    price_above_all = False
            else:
                ma_details.append(f'EMA{period}=N/A ✗')
                price_above_all = False

        # Create log entry
        ma_str = ', '.join(ma_details)
        if price_above_all:
            passed_stocks.append(stock.id)
            debug['logs'].append(f'✓ {stock.tradingsymbol}: Price={current_price:.2f} | {ma_str} | PASSED')
        else:
            rejected_stocks.append(stock.id)
            debug['logs'].append(f'✗ {stock.tradingsymbol}: Price={current_price:.2f} | {ma_str} | REJECTED')

    # Filter query to only include passed stocks
    if passed_stocks:
        query = query.filter(Instrument.id.in_(passed_stocks))
    else:
        # No stocks passed - return empty query
        query = query.filter(Instrument.id == -1)  # Impossible condition to return empty set

    final_count = len(passed_stocks)

    debug['logs'].append('')
    debug['logs'].append(f'[MA_FILTER] ====== SUMMARY ======')
    debug['logs'].append(f'[MA_FILTER] Total stocks analyzed: {initial_count}')
    debug['logs'].append(f'[MA_FILTER] Stocks PASSED (price above all MAs): {final_count}')
    debug['logs'].append(f'[MA_FILTER] Stocks REJECTED: {len(rejected_stocks)}')

    debug['steps'].append({
        'description': 'Moving Average Filter',
        'details': f'Price must be above all selected MAs',
        'criteria': f'SMA: {selected_sma}, EMA: {selected_ema}',
        'count': final_count,
        'passed': final_count > 0
    })

    return query, debug


def _apply_volume_filter_debug(query, criteria):
    """Apply volume contraction filter with detailed debugging"""
    debug = {'steps': [], 'logs': []}

    selected_volume_status = criteria.get('selected_volume_status', [])
    selected_volume_classification = criteria.get('selected_volume_classification', [])

    debug['logs'].append(f'[VOLUME_FILTER] Volume Status: {selected_volume_status}')
    debug['logs'].append(f'[VOLUME_FILTER] Volume Classification: {selected_volume_classification}')

    initial_count = query.count()

    if selected_volume_status:
        query = query.filter(Instrument.volume_dryup_status.in_(selected_volume_status))
        query = query.filter(Instrument.volume_dryup_status.isnot(None))
        count = query.count()
        debug['logs'].append(f'[VOLUME_FILTER] After volume status filter: {count} stocks')
        debug['steps'].append({
            'description': 'Filter by Volume Dry-Up Status',
            'details': f'Eliminated {initial_count - count} stocks not matching status',
            'criteria': f'Status: {", ".join(selected_volume_status)}',
            'count': count,
            'passed': count > 0
        })
        initial_count = count

    if selected_volume_classification:
        query = query.filter(Instrument.volume_dryup_classification.in_(selected_volume_classification))
        query = query.filter(Instrument.volume_dryup_classification.isnot(None))
        count = query.count()
        debug['logs'].append(f'[VOLUME_FILTER] After volume classification filter: {count} stocks')
        debug['steps'].append({
            'description': 'Filter by Volume Dry-Up Classification',
            'details': f'Eliminated {initial_count - count} stocks not matching classification',
            'criteria': f'Classification: {", ".join(selected_volume_classification)}',
            'count': count,
            'passed': count > 0
        })

    if not selected_volume_status and not selected_volume_classification:
        debug['logs'].append(f'[VOLUME_FILTER] No volume filter applied')
        count = query.count()
        debug['steps'].append({
            'description': 'No Volume Contraction Filter Applied',
            'details': 'No volume criteria specified',
            'count': count,
            'passed': True
        })

    return query, debug


def _apply_price_action_filter_debug(query, criteria):
    """Apply price action filter with detailed debugging"""
    debug = {'steps': [], 'logs': []}

    selected_strategies = criteria.get('selected_price_action_strategies', [])
    lookback_days = criteria.get('price_action_lookback_days', 252)

    debug['logs'].append(f'[PRICE_ACTION] Selected Strategies: {selected_strategies}')
    debug['logs'].append(f'[PRICE_ACTION] Lookback Period: {lookback_days} days')

    if not selected_strategies:
        debug['logs'].append(f'[PRICE_ACTION] No price action filter applied')
        count = query.count()
        debug['steps'].append({
            'description': 'No Price Action Filter Applied',
            'details': 'No price action strategies selected',
            'count': count,
            'passed': True
        })
        return query, debug

    # Get initial count
    initial_count = query.count()
    debug['logs'].append(f'[PRICE_ACTION] Initial stock count: {initial_count}')

    # Collect stock IDs that match price action patterns
    matching_stock_ids = []
    breakout_count = 0
    pullback_count = 0

    # Process each stock in the query
    for stock in query.all():
        try:
            # Get historical data
            hist_data = HistoricalData.query.filter_by(
                tradingsymbol=stock.tradingsymbol,
                interval='day'
            ).first()

            if not hist_data:
                continue

            candles = hist_data.get_candles()
            if not candles or len(candles) < lookback_days + 50:
                continue

            # Analyze patterns based on selected strategies
            matches_pattern = False

            if 'breakout' in selected_strategies:
                if _is_breakout_pattern(candles, lookback_days):
                    matches_pattern = True
                    breakout_count += 1
                    debug['logs'].append(f'[PRICE_ACTION] {stock.tradingsymbol}: BREAKOUT detected')

            if 'pullback' in selected_strategies:
                if _is_pullback_pattern(candles, lookback_days):
                    matches_pattern = True
                    pullback_count += 1
                    debug['logs'].append(f'[PRICE_ACTION] {stock.tradingsymbol}: PULLBACK detected')

            if matches_pattern:
                matching_stock_ids.append(stock.id)

        except Exception as e:
            debug['logs'].append(f'[PRICE_ACTION] Error analyzing {stock.tradingsymbol}: {str(e)}')
            continue

    # Apply filter to query
    if matching_stock_ids:
        query = query.filter(Instrument.id.in_(matching_stock_ids))
    else:
        # No stocks match - return empty query
        query = query.filter(Instrument.id == -1)

    final_count = len(matching_stock_ids)
    debug['logs'].append(f'[PRICE_ACTION] Breakout patterns found: {breakout_count}')
    debug['logs'].append(f'[PRICE_ACTION] Pullback patterns found: {pullback_count}')
    debug['logs'].append(f'[PRICE_ACTION] Total matching stocks: {final_count}')

    debug['steps'].append({
        'description': 'Price Action Pattern Filter',
        'details': f'Strategies: {", ".join(selected_strategies)} | Lookback: {lookback_days} days',
        'criteria': f'Breakout: {breakout_count}, Pullback: {pullback_count}',
        'count': final_count,
        'passed': True
    })

    return query, debug


def _is_breakout_pattern(candles, lookback_days):
    """
    Detect breakout pattern:
    - Price breaks above resistance (52-week high within lookback period)
    - Strong volume on breakout
    - Price sustains above breakout level
    """
    try:
        # Get lookback window
        lookback_candles = candles[-lookback_days:]
        if len(lookback_candles) < 20:
            return False

        # Get current price and recent high
        current_price = lookback_candles[-1]['close']

        # Find highest high in the lookback period (excluding last 5 days)
        resistance_high = max(c['high'] for c in lookback_candles[:-5])

        # Find if there was a recent breakout (in last 5 days)
        recent_candles = lookback_candles[-5:]

        # Check if any recent candle broke above resistance
        breakout_detected = False
        for candle in recent_candles:
            if candle['high'] > resistance_high * 1.01:  # 1% above resistance
                breakout_detected = True
                break

        if not breakout_detected:
            return False

        # Verify price is still above resistance (sustained breakout)
        if current_price < resistance_high * 0.98:  # More than 2% below
            return False

        # Check for volume confirmation
        avg_volume = sum(c['volume'] for c in lookback_candles[:-5]) / (len(lookback_candles) - 5)
        recent_volume = sum(c['volume'] for c in recent_candles) / len(recent_candles)

        # Volume should be at least 120% of average
        if recent_volume < avg_volume * 1.2:
            return False

        return True

    except Exception:
        return False


def _is_pullback_pattern(candles, lookback_days):
    """
    Detect pullback pattern:
    - Stock had a recent breakout
    - Price is now pulling back to support
    - Pullback is healthy (10-20% from high)
    - Volume is decreasing on pullback
    """
    try:
        # Get lookback window
        lookback_candles = candles[-lookback_days:]
        if len(lookback_candles) < 30:
            return False

        current_price = lookback_candles[-1]['close']

        # Find recent high (within last 30 days)
        recent_high_period = lookback_candles[-30:]
        recent_high = max(c['high'] for c in recent_high_period)

        # Calculate pullback percentage
        pullback_pct = ((recent_high - current_price) / recent_high) * 100

        # Check if in healthy pullback range (5% to 25%)
        if pullback_pct < 5 or pullback_pct > 25:
            return False

        # Check if price is above 50-day MA (still in uptrend)
        if len(lookback_candles) >= 50:
            ma_50 = sum(c['close'] for c in lookback_candles[-50:]) / 50
            if current_price < ma_50 * 0.95:  # More than 5% below MA
                return False

        # Check for decreasing volume on pullback (sign of healthy correction)
        recent_10_days = lookback_candles[-10:]
        prev_10_days = lookback_candles[-20:-10]

        recent_avg_volume = sum(c['volume'] for c in recent_10_days) / 10
        prev_avg_volume = sum(c['volume'] for c in prev_10_days) / 10

        # Volume should be lower (less selling pressure)
        if recent_avg_volume > prev_avg_volume * 1.1:
            return False

        return True

    except Exception:
        return False
