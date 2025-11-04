from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Instrument, Watchlist, WatchlistItem, SubSector, Sector
from app.market_data import MarketDataService
from app.stock_service import StockService
from sqlalchemy import or_

stocks_bp = Blueprint('stocks', __name__, url_prefix='/stocks')


@stocks_bp.route('/')
@login_required
def index():
    """Stocks listing page with filters - NIFTY 500 only"""
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '', type=str)
    sector_id = request.args.get('sector_id', '', type=str)
    sub_sector_id = request.args.get('sub_sector_id', '', type=str)

    # Base query - only NIFTY 500 stocks (NSE, EQ type)
    query = Instrument.query.filter_by(
        exchange='NSE',
        instrument_type='EQ',
        is_nifty500=True
    )

    # Apply filters
    if search:
        query = query.filter(
            or_(
                Instrument.tradingsymbol.ilike(f'%{search}%'),
                Instrument.name.ilike(f'%{search}%')
            )
        )

    # Filter by sub-sector (more specific) or sector (broader)
    if sub_sector_id:
        # If sub-sector is selected, filter by sub-sector
        try:
            sub_sector_id_int = int(sub_sector_id)
            query = query.filter(Instrument.sub_sector_id == sub_sector_id_int)
        except (ValueError, TypeError):
            pass  # Invalid sub_sector_id, ignore filter
    elif sector_id:
        # If only sector is selected, filter by sector (using sub_sector relationship)
        try:
            sector_id_int = int(sector_id)
            query = query.join(SubSector).filter(SubSector.sector_id == sector_id_int)
        except (ValueError, TypeError):
            pass  # Invalid sector_id, ignore filter

    # Order by trading symbol
    query = query.order_by(Instrument.tradingsymbol)

    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    stocks = pagination.items

    # Get active sectors from Sector model (that have stocks assigned)
    sectors_with_stocks = db.session.query(Sector).join(SubSector).join(Instrument).filter(
        Sector.is_active == True,
        Instrument.exchange == 'NSE',
        Instrument.instrument_type == 'EQ',
        Instrument.is_nifty500 == True
    ).distinct().order_by(Sector.display_order, Sector.name).all()

    # Get user's watchlists for quick add
    watchlists = current_user.watchlists.all()

    # Get total NIFTY 500 count
    total_nifty500 = Instrument.query.filter_by(
        exchange='NSE',
        instrument_type='EQ',
        is_nifty500=True
    ).count()

    return render_template('stocks/index.html',
                         title='NIFTY 500 Stocks',
                         stocks=stocks,
                         pagination=pagination,
                         sectors=sectors_with_stocks,
                         watchlists=watchlists,
                         search=search,
                         selected_sector_id=sector_id,
                         selected_sub_sector_id=sub_sector_id,
                         total_nifty500=total_nifty500)


@stocks_bp.route('/<symbol>')
@login_required
def detail(symbol):
    """Stock detail page - NIFTY 500 only"""
    # Find instrument by trading symbol (NIFTY 500 stocks only)
    instrument = Instrument.query.filter_by(
        tradingsymbol=symbol,
        exchange='NSE',
        instrument_type='EQ',
        is_nifty500=True
    ).first_or_404()

    # Get user's watchlists
    watchlists = current_user.watchlists.all()

    # Check if stock is in any watchlist
    in_watchlist = WatchlistItem.query.join(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        WatchlistItem.instrument_id == instrument.id
    ).first() is not None

    # Get all active sectors with subsectors for sector editing
    sectors = Sector.query.filter_by(is_active=True).order_by(
        Sector.display_order, Sector.name
    ).all()

    return render_template('stocks/detail.html',
                         title=f'{symbol} - Stock Detail',
                         instrument=instrument,
                         watchlists=watchlists,
                         in_watchlist=in_watchlist,
                         sectors=sectors)


@stocks_bp.route('/<symbol>/update-sector', methods=['POST'])
@login_required
def update_sector(symbol):
    """Update sector classification for a stock"""
    try:
        # Find the instrument
        instrument = Instrument.query.filter_by(
            tradingsymbol=symbol,
            exchange='NSE',
            instrument_type='EQ',
            is_nifty500=True
        ).first_or_404()

        # Get form data
        sub_sector_id = request.form.get('sub_sector_id')

        # Validate sub_sector_id
        if sub_sector_id:
            try:
                sub_sector_id = int(sub_sector_id)
                # Verify subsector exists
                subsector = SubSector.query.get(sub_sector_id)
                if not subsector:
                    flash('Invalid sub-sector selected', 'danger')
                    return redirect(url_for('stocks.detail', symbol=symbol))
            except (ValueError, TypeError):
                sub_sector_id = None

        # Update the instrument
        instrument.sub_sector_id = sub_sector_id
        db.session.commit()

        if sub_sector_id:
            subsector = SubSector.query.get(sub_sector_id)
            flash(f'Sector classification updated to {subsector.sector.name} → {subsector.name}', 'success')
        else:
            flash('Sector classification removed', 'info')

        return redirect(url_for('stocks.detail', symbol=symbol))

    except Exception as e:
        db.session.rollback()
        flash(f'Error updating sector: {str(e)}', 'danger')
        return redirect(url_for('stocks.detail', symbol=symbol))


@stocks_bp.route('/api/quote/<int:instrument_token>')
@login_required
def get_quote(instrument_token):
    """Get real-time quote for an instrument"""
    try:
        if not current_user.kite_access_token:
            return jsonify({'error': 'Kite not connected'}), 401

        market_service = MarketDataService(current_user.kite_access_token)
        quote = market_service.get_quote([instrument_token])

        if quote and str(instrument_token) in quote:
            return jsonify(quote[str(instrument_token)])
        else:
            return jsonify({'error': 'Quote not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stocks_bp.route('/api/search')
@login_required
def search():
    """Search stocks by symbol or name (AJAX endpoint) - NIFTY 500 only"""
    query = request.args.get('q', '', type=str)
    limit = request.args.get('limit', 10, type=int)

    if len(query) < 2:
        return jsonify([])

    # Search in tradingsymbol and name (NIFTY 500 stocks only)
    results = Instrument.query.filter(
        Instrument.exchange == 'NSE',
        Instrument.instrument_type == 'EQ',
        Instrument.is_nifty500 == True,
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


@stocks_bp.route('/sync', methods=['POST'])
@login_required
def sync_instruments():
    """Sync instruments from Kite Connect"""
    try:
        if not current_user.kite_access_token:
            flash('Please connect to Kite first.', 'warning')
            return redirect(url_for('stocks.index'))

        from app.instruments_manager import InstrumentsManager

        # Sync instruments from NSE
        stats = InstrumentsManager.sync_instruments(exchange='NSE')

        flash(f'Successfully synced instruments from Kite! Created: {stats["created"]}, Updated: {stats["updated"]}, Total: {stats["total"]}', 'success')

    except Exception as e:
        flash(f'Error syncing instruments: {str(e)}', 'danger')

    return redirect(url_for('stocks.index'))


@stocks_bp.route('/add-to-watchlist', methods=['POST'])
@login_required
def add_to_watchlist():
    """Add stock to watchlist"""
    try:
        instrument_id = request.form.get('instrument_id', type=int)
        watchlist_id = request.form.get('watchlist_id', type=int)
        notes = request.form.get('notes', '')

        if not instrument_id or not watchlist_id:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400

        # Verify watchlist belongs to current user
        watchlist = Watchlist.query.filter_by(id=watchlist_id, user_id=current_user.id).first()
        if not watchlist:
            return jsonify({'success': False, 'error': 'Watchlist not found'}), 404

        # Check if already in watchlist
        existing = WatchlistItem.query.filter_by(
            watchlist_id=watchlist_id,
            instrument_id=instrument_id
        ).first()

        if existing:
            return jsonify({'success': False, 'error': 'Already in watchlist'}), 400

        # Add to watchlist
        item = WatchlistItem(
            watchlist_id=watchlist_id,
            instrument_id=instrument_id,
            notes=notes
        )
        db.session.add(item)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Added to watchlist'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# CRUD Operations for Stocks

@stocks_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_stock():
    """Add a new stock by symbol"""
    if request.method == 'POST':
        symbol = request.form.get('symbol', '').strip().upper()
        exchange = request.form.get('exchange', 'NSE')

        if not symbol:
            flash('Please enter a stock symbol', 'danger')
            return render_template('stocks/add.html', title='Add Stock')

        # Check if user is connected to Kite
        if not current_user.kite_access_token:
            flash('Please connect to Kite first to add stocks', 'warning')
            return redirect(url_for('kite_auth.connect'))

        # Add stock using StockService
        stock, error = StockService.add_stock(symbol, exchange)

        if error:
            flash(error, 'danger')
            return render_template('stocks/add.html', title='Add Stock', symbol=symbol)

        flash(f'Stock {symbol} ({stock.name}) added successfully!', 'success')
        return redirect(url_for('stocks.detail', symbol=stock.tradingsymbol))

    return render_template('stocks/add.html', title='Add Stock')


@stocks_bp.route('/<int:stock_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_stock(stock_id):
    """Edit an existing stock"""
    stock = StockService.get_stock(stock_id)

    if not stock:
        flash('Stock not found', 'danger')
        return redirect(url_for('stocks.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        sub_sector_id = request.form.get('sub_sector_id', type=int)

        # If empty sub_sector_id, set to None
        if sub_sector_id == 0 or sub_sector_id == '':
            sub_sector_id = None

        updated_stock, error = StockService.update_stock(
            stock_id=stock_id,
            name=name if name else None,
            sub_sector_id=sub_sector_id
        )

        if error:
            flash(error, 'danger')
        else:
            flash(f'Stock {updated_stock.tradingsymbol} updated successfully!', 'success')
            return redirect(url_for('stocks.detail', symbol=updated_stock.tradingsymbol))

    # Get all active sectors with sub-sectors for dropdown
    sectors = Sector.query.filter_by(is_active=True).order_by(Sector.display_order, Sector.name).all()

    return render_template('stocks/edit.html',
                         title=f'Edit {stock.tradingsymbol}',
                         stock=stock,
                         sectors=sectors)


@stocks_bp.route('/<int:stock_id>/delete', methods=['POST'])
@login_required
def delete_stock(stock_id):
    """Delete a stock"""
    stock = StockService.get_stock(stock_id)

    if not stock:
        flash('Stock not found', 'danger')
        return redirect(url_for('stocks.index'))

    symbol = stock.tradingsymbol

    success, error = StockService.delete_stock(stock_id)

    if error:
        flash(error, 'danger')
    else:
        flash(f'Stock {symbol} deleted successfully!', 'success')

    return redirect(url_for('stocks.index'))
