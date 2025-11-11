"""
Aligned Breakout Strategy - API Endpoints

Provides REST API for accessing:
- Stock metrics (RS, stage, volume, etc.)
- Sector/SubSector metrics
- Scanner profiles
- Scan results and watchlist

Author: Claude Code
"""

from flask import Blueprint, jsonify, request, render_template
from app.models import (
    Instrument, Sector, SubSector,
    AlignedBreakoutStockMetrics, AlignedBreakoutSectorMetrics,
    AlignedBreakoutProfile, AlignedBreakoutScanResult,
    AlignedBreakoutWatchlist, AlignedBreakoutRSHistory
)
from app.services.aligned_breakout_calculator import AlignedBreakoutCalculator
from datetime import date
from sqlalchemy import desc

aligned_breakout_api = Blueprint('aligned_breakout_api', __name__, url_prefix='/api/aligned-breakout')


@aligned_breakout_api.route('/dashboard', methods=['GET'])
def dashboard():
    """Render Aligned Breakout dashboard UI"""
    return render_template('aligned_breakout_dashboard.html')


@aligned_breakout_api.route('/stocks', methods=['GET'])
def get_stocks_with_metrics():
    """
    Get all stocks with their Aligned Breakout metrics

    Query params:
        stage: Filter by stage (1-4)
        rs_min: Minimum RS vs Nifty 50
        limit: Max results (default 50)
        sort: Sort field (rs_vs_nifty50, ma_150_slope, etc.)
    """
    # Get query parameters
    stage = request.args.get('stage', type=int)
    rs_min = request.args.get('rs_min', type=float, default=0)
    limit = request.args.get('limit', type=int, default=50)
    sort_by = request.args.get('sort', default='rs_vs_nifty50')

    # Build query
    query = AlignedBreakoutStockMetrics.query.join(
        Instrument, AlignedBreakoutStockMetrics.instrument_id == Instrument.id
    )

    # Apply filters
    if stage:
        query = query.filter(AlignedBreakoutStockMetrics.current_stage == stage)

    if rs_min > 0:
        query = query.filter(AlignedBreakoutStockMetrics.rs_vs_nifty50 >= rs_min)

    # Sort
    if sort_by == 'rs_vs_nifty50':
        query = query.order_by(desc(AlignedBreakoutStockMetrics.rs_vs_nifty50))
    elif sort_by == 'ma_150_slope':
        query = query.order_by(desc(AlignedBreakoutStockMetrics.ma_150_slope))
    else:
        query = query.order_by(desc(AlignedBreakoutStockMetrics.rs_vs_nifty50))

    # Limit results
    metrics = query.limit(limit).all()

    # Build response
    results = []
    for m in metrics:
        results.append({
            'symbol': m.instrument.tradingsymbol,
            'price': m.instrument.last_price,
            'stage': m.current_stage,
            'weeks_in_stage': m.weeks_in_stage,
            'rs_vs_nifty50': m.rs_vs_nifty50,
            'rs_trend': m.rs_vs_nifty50_trend,
            'ma_150_value': m.ma_150_value,
            'ma_150_slope': m.ma_150_slope,
            'week_52_high': m.week_52_high,
            'distance_from_52w_high_pct': m.distance_from_52w_high_pct,
            'volume_breakout': m.volume_breakout_detected,
            'accumulation_days': m.accumulation_pattern_days,
            'sector': m.instrument.sub_sector.sector.name if m.instrument.sub_sector else None,
            'subsector': m.instrument.sub_sector.name if m.instrument.sub_sector else None,
            'calculated_at': m.calculated_at.isoformat() if m.calculated_at else None
        })

    return jsonify({
        'success': True,
        'count': len(results),
        'stocks': results
    })


@aligned_breakout_api.route('/stocks/<symbol>', methods=['GET'])
def get_stock_metrics(symbol):
    """Get detailed metrics for a specific stock"""
    instrument = Instrument.query.filter_by(tradingsymbol=symbol).first()

    if not instrument:
        return jsonify({'success': False, 'error': 'Stock not found'}), 404

    metrics = AlignedBreakoutStockMetrics.query.filter_by(instrument_id=instrument.id).first()

    if not metrics:
        return jsonify({'success': False, 'error': 'Metrics not calculated'}), 404

    # Get RS history
    rs_history = AlignedBreakoutRSHistory.query.filter_by(
        entity_type='stock',
        instrument_id=instrument.id
    ).order_by(desc(AlignedBreakoutRSHistory.calculated_date)).limit(30).all()

    return jsonify({
        'success': True,
        'stock': {
            'symbol': instrument.tradingsymbol,
            'name': instrument.name,
            'price': instrument.last_price,
            'exchange': instrument.exchange,
            'sector': instrument.sub_sector.sector.name if instrument.sub_sector else None,
            'subsector': instrument.sub_sector.name if instrument.sub_sector else None
        },
        'metrics': {
            'stage': metrics.current_stage,
            'weeks_in_stage': metrics.weeks_in_stage,
            'stage_entry_date': metrics.stage_entry_date.isoformat() if metrics.stage_entry_date else None,
            'rs_vs_nifty50': metrics.rs_vs_nifty50,
            'rs_trend': metrics.rs_vs_nifty50_trend,
            'ma_150_value': metrics.ma_150_value,
            'ma_150_slope': metrics.ma_150_slope,
            'week_52_high': metrics.week_52_high,
            'week_52_low': metrics.week_52_low,
            'distance_from_52w_high_pct': metrics.distance_from_52w_high_pct,
            'avg_volume_50d': metrics.avg_volume_50d,
            'last_volume': metrics.last_volume,
            'volume_breakout_detected': metrics.volume_breakout_detected,
            'accumulation_pattern_days': metrics.accumulation_pattern_days,
            'calculated_at': metrics.calculated_at.isoformat() if metrics.calculated_at else None
        },
        'rs_history': [
            {
                'date': h.calculated_date.isoformat(),
                'rs_value': h.rs_vs_nifty50
            } for h in rs_history
        ]
    })


@aligned_breakout_api.route('/sectors', methods=['GET'])
def get_sectors():
    """Get all sectors with their RS metrics"""
    sectors = AlignedBreakoutSectorMetrics.query.filter_by(
        entity_type='sector'
    ).join(
        Sector, AlignedBreakoutSectorMetrics.sector_id == Sector.id
    ).order_by(desc(AlignedBreakoutSectorMetrics.rs_vs_nifty50)).all()

    results = []
    for m in sectors:
        # Count stocks in this sector
        stock_count = Instrument.query.join(SubSector).filter(
            SubSector.sector_id == m.sector.id
        ).count()

        results.append({
            'id': m.sector.id,
            'name': m.sector.name,
            'rs_vs_nifty50': m.rs_vs_nifty50,
            'rs_trend': m.rs_vs_nifty50_trend,
            'current_stage': m.current_stage,
            'weeks_in_stage': m.weeks_in_stage,
            'stock_count': stock_count,
            'calculated_at': m.calculated_at.isoformat() if m.calculated_at else None
        })

    return jsonify({
        'success': True,
        'count': len(results),
        'sectors': results
    })


@aligned_breakout_api.route('/subsectors', methods=['GET'])
def get_subsectors():
    """
    Get all subsectors with their RS metrics

    Query params:
        sector_id: Filter by sector
        rs_min: Minimum RS vs Nifty 50
    """
    sector_id = request.args.get('sector_id', type=int)
    rs_min = request.args.get('rs_min', type=float, default=0)

    query = AlignedBreakoutSectorMetrics.query.filter_by(
        entity_type='subsector'
    ).join(
        SubSector, AlignedBreakoutSectorMetrics.subsector_id == SubSector.id
    )

    if sector_id:
        query = query.filter(SubSector.sector_id == sector_id)

    if rs_min > 0:
        query = query.filter(AlignedBreakoutSectorMetrics.rs_vs_nifty50 >= rs_min)

    subsectors = query.order_by(desc(AlignedBreakoutSectorMetrics.rs_vs_nifty50)).all()

    results = []
    for m in subsectors:
        # Count stocks in this subsector
        stock_count = Instrument.query.filter_by(sub_sector_id=m.subsector.id).count()

        results.append({
            'id': m.subsector.id,
            'name': m.subsector.name,
            'sector_name': m.subsector.sector.name,
            'sector_id': m.subsector.sector_id,
            'rs_vs_nifty50': m.rs_vs_nifty50,
            'rs_trend': m.rs_vs_nifty50_trend,
            'current_stage': m.current_stage,
            'weeks_in_stage': m.weeks_in_stage,
            'stock_count': stock_count,
            'calculated_at': m.calculated_at.isoformat() if m.calculated_at else None
        })

    return jsonify({
        'success': True,
        'count': len(results),
        'subsectors': results
    })


@aligned_breakout_api.route('/top-performers', methods=['GET'])
def get_top_performers():
    """Get top performing stocks across all metrics"""
    limit = request.args.get('limit', type=int, default=20)

    # Top RS stocks
    top_rs = AlignedBreakoutStockMetrics.query.join(
        Instrument
    ).filter(
        AlignedBreakoutStockMetrics.rs_vs_nifty50 != None
    ).order_by(
        desc(AlignedBreakoutStockMetrics.rs_vs_nifty50)
    ).limit(limit).all()

    # Top MA slope (strongest uptrends)
    top_slope = AlignedBreakoutStockMetrics.query.join(
        Instrument
    ).filter(
        AlignedBreakoutStockMetrics.ma_150_slope != None,
        AlignedBreakoutStockMetrics.ma_150_slope > 0
    ).order_by(
        desc(AlignedBreakoutStockMetrics.ma_150_slope)
    ).limit(limit).all()

    # Stage 2 with improving RS trend
    stage2_improving = AlignedBreakoutStockMetrics.query.join(
        Instrument
    ).filter(
        AlignedBreakoutStockMetrics.current_stage == 2,
        AlignedBreakoutStockMetrics.rs_vs_nifty50_trend == 'improving'
    ).order_by(
        desc(AlignedBreakoutStockMetrics.rs_vs_nifty50)
    ).limit(limit).all()

    def format_stock(m):
        return {
            'symbol': m.instrument.tradingsymbol,
            'price': m.instrument.last_price,
            'stage': m.current_stage,
            'rs_vs_nifty50': m.rs_vs_nifty50,
            'rs_trend': m.rs_vs_nifty50_trend,
            'ma_150_slope': m.ma_150_slope
        }

    return jsonify({
        'success': True,
        'top_rs': [format_stock(m) for m in top_rs],
        'top_uptrend': [format_stock(m) for m in top_slope],
        'stage2_improving': [format_stock(m) for m in stage2_improving]
    })


@aligned_breakout_api.route('/update-metrics', methods=['POST'])
def trigger_metrics_update():
    """Trigger metrics recalculation (use with caution - slow operation)"""
    from app.services.aligned_breakout_calculator import update_aligned_breakout_metrics

    limit = request.json.get('limit') if request.json else None

    try:
        result = update_aligned_breakout_metrics(limit=limit)

        return jsonify({
            'success': True,
            'message': 'Metrics updated successfully',
            'stats': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@aligned_breakout_api.route('/update-rs-trends', methods=['POST'])
def trigger_rs_trends_update():
    """Trigger RS trend calculation (daily job)"""
    calc = AlignedBreakoutCalculator()

    try:
        result = calc.update_all_rs_trends()

        return jsonify({
            'success': True,
            'message': 'RS trends updated successfully',
            'stats': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@aligned_breakout_api.route('/stats', methods=['GET'])
def get_statistics():
    """Get overall statistics about the Aligned Breakout metrics"""
    from sqlalchemy import func

    # Stock stats
    total_stocks = AlignedBreakoutStockMetrics.query.count()
    stage_dist = AlignedBreakoutStockMetrics.query.with_entities(
        AlignedBreakoutStockMetrics.current_stage,
        func.count(AlignedBreakoutStockMetrics.id)
    ).group_by(AlignedBreakoutStockMetrics.current_stage).all()

    rs_avg = AlignedBreakoutStockMetrics.query.with_entities(
        func.avg(AlignedBreakoutStockMetrics.rs_vs_nifty50)
    ).scalar()

    # Sector stats
    total_sectors = AlignedBreakoutSectorMetrics.query.filter_by(entity_type='sector').count()
    total_subsectors = AlignedBreakoutSectorMetrics.query.filter_by(entity_type='subsector').count()

    # RS history stats
    total_snapshots = AlignedBreakoutRSHistory.query.count()
    latest_snapshot = AlignedBreakoutRSHistory.query.order_by(
        desc(AlignedBreakoutRSHistory.calculated_date)
    ).first()

    return jsonify({
        'success': True,
        'stats': {
            'stocks': {
                'total': total_stocks,
                'stage_distribution': {int(stage): count for stage, count in stage_dist},
                'avg_rs': round(rs_avg, 2) if rs_avg else None
            },
            'sectors': {
                'total': total_sectors
            },
            'subsectors': {
                'total': total_subsectors
            },
            'rs_history': {
                'total_snapshots': total_snapshots,
                'latest_date': latest_snapshot.calculated_date.isoformat() if latest_snapshot else None
            }
        }
    })
