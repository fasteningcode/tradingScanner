from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Watchlist, WatchlistItem, Instrument
from app.market_data import MarketDataService
from datetime import datetime

watchlist_bp = Blueprint('watchlist', __name__, url_prefix='/watchlist')


@watchlist_bp.route('/')
@login_required
def index():
    """List all watchlists for the current user"""
    watchlists = current_user.watchlists.all()

    # Get item count for each watchlist
    watchlist_data = []
    for wl in watchlists:
        watchlist_data.append({
            'watchlist': wl,
            'item_count': wl.items.count()
        })

    return render_template('watchlist/index.html',
                         title='My Watchlists',
                         watchlist_data=watchlist_data)


@watchlist_bp.route('/<int:watchlist_id>')
@login_required
def view(watchlist_id):
    """View a specific watchlist with live quotes"""
    watchlist = Watchlist.query.filter_by(id=watchlist_id, user_id=current_user.id).first_or_404()

    # Get all items with their instruments
    items = watchlist.items.all()

    return render_template('watchlist/view.html',
                         title=f'{watchlist.name} - Watchlist',
                         watchlist=watchlist,
                         items=items)


@watchlist_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new watchlist"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if not name:
            flash('Watchlist name is required.', 'danger')
            return redirect(url_for('watchlist.create'))

        # Check if watchlist with same name exists
        existing = Watchlist.query.filter_by(user_id=current_user.id, name=name).first()
        if existing:
            flash('A watchlist with this name already exists.', 'warning')
            return redirect(url_for('watchlist.create'))

        try:
            watchlist = Watchlist(
                user_id=current_user.id,
                name=name,
                description=description
            )
            db.session.add(watchlist)
            db.session.commit()

            flash(f'Watchlist "{name}" created successfully!', 'success')
            return redirect(url_for('watchlist.view', watchlist_id=watchlist.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating watchlist: {str(e)}', 'danger')
            return redirect(url_for('watchlist.create'))

    return render_template('watchlist/create.html', title='Create Watchlist')


@watchlist_bp.route('/<int:watchlist_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(watchlist_id):
    """Edit a watchlist"""
    watchlist = Watchlist.query.filter_by(id=watchlist_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if not name:
            flash('Watchlist name is required.', 'danger')
            return redirect(url_for('watchlist.edit', watchlist_id=watchlist_id))

        # Check if another watchlist with same name exists
        existing = Watchlist.query.filter(
            Watchlist.user_id == current_user.id,
            Watchlist.name == name,
            Watchlist.id != watchlist_id
        ).first()

        if existing:
            flash('A watchlist with this name already exists.', 'warning')
            return redirect(url_for('watchlist.edit', watchlist_id=watchlist_id))

        try:
            watchlist.name = name
            watchlist.description = description
            db.session.commit()

            flash(f'Watchlist "{name}" updated successfully!', 'success')
            return redirect(url_for('watchlist.view', watchlist_id=watchlist.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating watchlist: {str(e)}', 'danger')

    return render_template('watchlist/edit.html',
                         title=f'Edit {watchlist.name}',
                         watchlist=watchlist)


@watchlist_bp.route('/<int:watchlist_id>/delete', methods=['POST'])
@login_required
def delete(watchlist_id):
    """Delete a watchlist"""
    watchlist = Watchlist.query.filter_by(id=watchlist_id, user_id=current_user.id).first_or_404()

    try:
        name = watchlist.name
        db.session.delete(watchlist)
        db.session.commit()

        flash(f'Watchlist "{name}" deleted successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting watchlist: {str(e)}', 'danger')

    return redirect(url_for('watchlist.index'))


@watchlist_bp.route('/<int:watchlist_id>/remove-item/<int:item_id>', methods=['POST'])
@login_required
def remove_item(watchlist_id, item_id):
    """Remove an item from watchlist"""
    watchlist = Watchlist.query.filter_by(id=watchlist_id, user_id=current_user.id).first_or_404()
    item = WatchlistItem.query.filter_by(id=item_id, watchlist_id=watchlist_id).first_or_404()

    try:
        db.session.delete(item)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Item removed from watchlist'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@watchlist_bp.route('/<int:watchlist_id>/update-notes/<int:item_id>', methods=['POST'])
@login_required
def update_notes(watchlist_id, item_id):
    """Update notes for a watchlist item"""
    watchlist = Watchlist.query.filter_by(id=watchlist_id, user_id=current_user.id).first_or_404()
    item = WatchlistItem.query.filter_by(id=item_id, watchlist_id=watchlist_id).first_or_404()

    try:
        notes = request.form.get('notes', '').strip()
        item.notes = notes
        db.session.commit()

        return jsonify({'success': True, 'message': 'Notes updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@watchlist_bp.route('/api/quotes/<int:watchlist_id>')
@login_required
def get_quotes(watchlist_id):
    """Get real-time quotes for all instruments in a watchlist"""
    try:
        watchlist = Watchlist.query.filter_by(id=watchlist_id, user_id=current_user.id).first_or_404()

        if not current_user.kite_access_token:
            return jsonify({'error': 'Kite not connected'}), 401

        # Get all instrument tokens from watchlist
        items = watchlist.items.all()
        if not items:
            return jsonify({'quotes': {}})

        instrument_tokens = [item.instrument.instrument_token for item in items]

        # Fetch quotes from Kite
        market_service = MarketDataService(current_user.kite_access_token)
        quotes = market_service.get_quote(instrument_tokens)

        if quotes:
            return jsonify({'quotes': quotes})
        else:
            return jsonify({'error': 'Failed to fetch quotes'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@watchlist_bp.route('/api/search')
@login_required
def search_stocks():
    """Search stocks to add to watchlist (AJAX endpoint)"""
    query = request.args.get('q', '', type=str)
    limit = request.args.get('limit', 20, type=int)

    if len(query) < 2:
        return jsonify([])

    # Search in tradingsymbol and name
    from sqlalchemy import or_
    results = Instrument.query.filter(
        Instrument.instrument_type == 'EQ',
        or_(
            Instrument.tradingsymbol.ilike(f'%{query}%'),
            Instrument.name.ilike(f'%{query}%')
        )
    ).limit(limit).all()

    return jsonify([{
        'id': r.id,
        'token': r.instrument_token,
        'symbol': r.tradingsymbol,
        'name': r.name,
        'exchange': r.exchange
    } for r in results])


@watchlist_bp.route('/<int:watchlist_id>/add-stock', methods=['POST'])
@login_required
def add_stock(watchlist_id):
    """Add a stock to watchlist via AJAX"""
    try:
        watchlist = Watchlist.query.filter_by(id=watchlist_id, user_id=current_user.id).first_or_404()

        instrument_id = request.form.get('instrument_id', type=int)
        notes = request.form.get('notes', '').strip()

        if not instrument_id:
            return jsonify({'success': False, 'error': 'Instrument ID is required'}), 400

        # Check if already in watchlist
        existing = WatchlistItem.query.filter_by(
            watchlist_id=watchlist_id,
            instrument_id=instrument_id
        ).first()

        if existing:
            return jsonify({'success': False, 'error': 'Stock already in watchlist'}), 400

        # Add to watchlist
        item = WatchlistItem(
            watchlist_id=watchlist_id,
            instrument_id=instrument_id,
            notes=notes
        )
        db.session.add(item)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Stock added to watchlist'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
