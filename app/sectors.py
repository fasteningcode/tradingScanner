from flask import Blueprint, render_template, current_app
from flask_login import login_required
from app.models import Sector, SubSector, Instrument
from app.index_service import IndexService
from app.historical_index_service import HistoricalIndexService
from sqlalchemy import func

sectors_bp = Blueprint('sectors', __name__, url_prefix='/sectors')


@sectors_bp.route('/')
@login_required
def index():
    """Sectors overview page with sectorial indices"""
    # Get all active sectors ordered by display_order
    sectors = Sector.query.filter_by(is_active=True).order_by(Sector.display_order, Sector.name).all()

    # Get market index from historical data (NIFTY500)
    market_index_data = HistoricalIndexService.get_index_with_change('NIFTY500')

    # Prepare sector data with statistics and indices
    sector_data = []
    for sector in sectors:
        # Count sub-sectors
        subsector_count = SubSector.query.filter_by(sector_id=sector.id, is_active=True).count()

        # Count stocks in this sector (through sub-sectors)
        stock_count = Instrument.query.join(SubSector).filter(
            SubSector.sector_id == sector.id,
            SubSector.is_active == True,
            Instrument.is_nifty500 == True
        ).count()

        # Get sector index from historical data
        index_data = None
        if sector.index_symbol:
            index_data = HistoricalIndexService.get_index_with_change(sector.index_symbol)

        sector_data.append({
            'sector': sector,
            'subsector_count': subsector_count,
            'stock_count': stock_count,
            'index_value': index_data.get('index_value') if index_data else None,
            'percentage_change': index_data.get('percentage_change') if index_data else None,
            'change_direction': index_data.get('change_direction') if index_data else 'neutral',
            'index_date': index_data.get('date') if index_data else None
        })

    return render_template('sectors/index.html',
                         title='Sectors',
                         sector_data=sector_data,
                         total_sectors=len(sectors),
                         market_index=market_index_data)


@sectors_bp.route('/<int:sector_id>')
@login_required
def view(sector_id):
    """View specific sector with subsector indices and stock contributions"""
    # Get the sector
    sector = Sector.query.get_or_404(sector_id)

    # Get sector index from historical data
    sector_index = None
    if sector.index_symbol:
        sector_index = HistoricalIndexService.get_index_with_change(sector.index_symbol)

    # Get all active subsectors
    subsectors = SubSector.query.filter_by(sector_id=sector_id, is_active=True).order_by(SubSector.name).all()

    # Prepare subsector data with indices
    subsector_data = []
    for subsector in subsectors:
        # Get subsector index from historical data
        index_data = None
        if subsector.index_symbol:
            index_data = HistoricalIndexService.get_index_with_change(subsector.index_symbol)

        # Get stock contributions
        stock_contributions = IndexService.get_subsector_stocks_contribution(subsector.id)

        subsector_data.append({
            'subsector': subsector,
            'index_value': index_data.get('index_value') if index_data else None,
            'percentage_change': index_data.get('percentage_change') if index_data else None,
            'change_direction': index_data.get('change_direction') if index_data else 'neutral',
            'index_date': index_data.get('date') if index_data else None,
            'stock_count': len(stock_contributions),
            'stocks': stock_contributions[:10]  # Top 10 contributors
        })

    return render_template('sectors/view.html',
                         title=f'{sector.name} - Sector Details',
                         sector=sector,
                         sector_index=sector_index,
                         subsector_data=subsector_data)


@sectors_bp.route('/heatmap')
@login_required
def heatmap():
    """Sector heatmap visualization page - Coming Soon"""
    return render_template('sectors/heatmap.html', title='Sector Heatmap')
