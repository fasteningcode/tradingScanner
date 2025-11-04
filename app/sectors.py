from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Sector, SubSector, Instrument
from sqlalchemy import func

sectors_bp = Blueprint('sectors', __name__, url_prefix='/sectors')


@sectors_bp.route('/')
@login_required
def index():
    """Sectors overview page"""
    # Get all active sectors ordered by display_order
    sectors = Sector.query.filter_by(is_active=True).order_by(Sector.display_order, Sector.name).all()

    # Prepare sector data with statistics
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

        sector_data.append({
            'sector': sector,
            'subsector_count': subsector_count,
            'stock_count': stock_count
        })

    return render_template('sectors/index.html',
                         title='Sectors',
                         sector_data=sector_data,
                         total_sectors=len(sectors))


@sectors_bp.route('/<int:sector_id>')
@login_required
def view(sector_id):
    """View specific sector - Coming Soon"""
    return render_template('sectors/view.html', title='Sector Details', sector_id=sector_id)


@sectors_bp.route('/heatmap')
@login_required
def heatmap():
    """Sector heatmap visualization page - Coming Soon"""
    return render_template('sectors/heatmap.html', title='Sector Heatmap')
