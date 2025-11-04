from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from kiteconnect import KiteConnect
import logging

positions_bp = Blueprint('positions', __name__, url_prefix='/positions')


@positions_bp.route('/')
@login_required
def index():
    """Positions main page - shows current positions and holdings"""
    if not current_user.kite_access_token:
        flash('Please connect to Kite to access positions', 'warning')
        return redirect(url_for('kite.connect'))

    return render_template('positions/index.html', title='Positions')


@positions_bp.route('/api/positions')
@login_required
def get_positions():
    """Get all current positions"""
    try:
        if not current_user.kite_access_token:
            return jsonify({'success': False, 'error': 'Kite not connected'}), 401

        kite = KiteConnect(api_key=current_user.kite_api_key)
        kite.set_access_token(current_user.kite_access_token)

        # Fetch positions
        positions = kite.positions()

        # Separate day and net positions
        day_positions = positions.get('day', [])
        net_positions = positions.get('net', [])

        # Calculate totals
        day_pnl = sum(p.get('pnl', 0) for p in day_positions)
        net_pnl = sum(p.get('pnl', 0) for p in net_positions)

        return jsonify({
            'success': True,
            'day_positions': day_positions,
            'net_positions': net_positions,
            'day_pnl': day_pnl,
            'net_pnl': net_pnl,
            'day_count': len([p for p in day_positions if p.get('quantity', 0) != 0]),
            'net_count': len([p for p in net_positions if p.get('quantity', 0) != 0])
        })

    except Exception as e:
        logging.error(f"Error fetching positions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/holdings')
@login_required
def get_holdings():
    """Get all holdings (long-term investments)"""
    try:
        if not current_user.kite_access_token:
            return jsonify({'success': False, 'error': 'Kite not connected'}), 401

        kite = KiteConnect(api_key=current_user.kite_api_key)
        kite.set_access_token(current_user.kite_access_token)

        # Fetch holdings
        holdings = kite.holdings()

        # Calculate totals
        total_investment = sum(h.get('average_price', 0) * h.get('quantity', 0) for h in holdings)
        total_current_value = sum(h.get('last_price', 0) * h.get('quantity', 0) for h in holdings)
        total_pnl = total_current_value - total_investment
        total_pnl_percent = (total_pnl / total_investment * 100) if total_investment > 0 else 0

        return jsonify({
            'success': True,
            'holdings': holdings,
            'count': len(holdings),
            'total_investment': total_investment,
            'total_current_value': total_current_value,
            'total_pnl': total_pnl,
            'total_pnl_percent': total_pnl_percent
        })

    except Exception as e:
        logging.error(f"Error fetching holdings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/convert', methods=['POST'])
@login_required
def convert_position():
    """Convert position between product types"""
    try:
        if not current_user.kite_access_token:
            return jsonify({'success': False, 'error': 'Kite not connected'}), 401

        data = request.json if request.is_json else request.form

        # Validate required fields
        required_fields = ['tradingsymbol', 'exchange', 'transaction_type',
                          'quantity', 'old_product', 'new_product']

        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        kite = KiteConnect(api_key=current_user.kite_api_key)
        kite.set_access_token(current_user.kite_access_token)

        # Convert position
        kite.convert_position(
            tradingsymbol=data.get('tradingsymbol'),
            exchange=data.get('exchange'),
            transaction_type=data.get('transaction_type'),
            position_type=data.get('position_type', 'day'),
            quantity=int(data.get('quantity')),
            old_product=data.get('old_product'),
            new_product=data.get('new_product')
        )

        logging.info(f"Position converted successfully for {data.get('tradingsymbol')}")

        return jsonify({
            'success': True,
            'message': 'Position converted successfully'
        })

    except Exception as e:
        logging.error(f"Error converting position: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/exit/<tradingsymbol>', methods=['POST'])
@login_required
def exit_position(tradingsymbol):
    """Exit a position by placing opposite order"""
    try:
        if not current_user.kite_access_token:
            return jsonify({'success': False, 'error': 'Kite not connected'}), 401

        data = request.json if request.is_json else request.form

        # Validate required fields
        required_fields = ['exchange', 'transaction_type', 'quantity', 'product']

        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        kite = KiteConnect(api_key=current_user.kite_api_key)
        kite.set_access_token(current_user.kite_access_token)

        # Determine opposite transaction type
        opposite_transaction = 'SELL' if data.get('transaction_type') == 'BUY' else 'BUY'

        # Place market order to exit position
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            tradingsymbol=tradingsymbol,
            exchange=data.get('exchange'),
            transaction_type=opposite_transaction,
            quantity=int(data.get('quantity')),
            order_type='MARKET',
            product=data.get('product')
        )

        logging.info(f"Exit order placed successfully: {order_id}")

        return jsonify({
            'success': True,
            'order_id': order_id,
            'message': f'Exit order placed successfully (ID: {order_id})'
        })

    except Exception as e:
        logging.error(f"Error exiting position: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@positions_bp.route('/api/margins')
@login_required
def get_margins():
    """Get margin details"""
    try:
        if not current_user.kite_access_token:
            return jsonify({'success': False, 'error': 'Kite not connected'}), 401

        kite = KiteConnect(api_key=current_user.kite_api_key)
        kite.set_access_token(current_user.kite_access_token)

        # Fetch margins
        margins = kite.margins()

        return jsonify({
            'success': True,
            'margins': margins
        })

    except Exception as e:
        logging.error(f"Error fetching margins: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
