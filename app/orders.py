from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Instrument
from kiteconnect import KiteConnect
import logging

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')

# Order types and transaction types
ORDER_TYPES = {
    'MARKET': 'Market Order',
    'LIMIT': 'Limit Order',
    'SL': 'Stop Loss',
    'SL-M': 'Stop Loss Market'
}

TRANSACTION_TYPES = {
    'BUY': 'Buy',
    'SELL': 'Sell'
}

PRODUCT_TYPES = {
    'CNC': 'Cash & Carry (Delivery)',
    'MIS': 'Intraday (MIS)',
    'NRML': 'Normal (F&O)'
}

VALIDITY_TYPES = {
    'DAY': 'Day Order',
    'IOC': 'Immediate or Cancel'
}


@orders_bp.route('/')
@login_required
def index():
    """Orders main page - shows order book and pending orders"""
    if not current_user.kite_access_token:
        flash('Please connect to Kite to access orders', 'warning')
        return redirect(url_for('kite.connect'))

    return render_template('orders/index.html',
                         title='Orders',
                         order_types=ORDER_TYPES,
                         transaction_types=TRANSACTION_TYPES,
                         product_types=PRODUCT_TYPES,
                         validity_types=VALIDITY_TYPES)


@orders_bp.route('/place')
@login_required
def place_order_form():
    """Place order form page"""
    if not current_user.kite_access_token:
        flash('Please connect to Kite to place orders', 'warning')
        return redirect(url_for('kite.connect'))

    # Get symbol from query params
    symbol = request.args.get('symbol', '')
    instrument = None

    if symbol:
        instrument = Instrument.query.filter_by(tradingsymbol=symbol).first()

    return render_template('orders/place.html',
                         title='Place Order',
                         instrument=instrument,
                         order_types=ORDER_TYPES,
                         transaction_types=TRANSACTION_TYPES,
                         product_types=PRODUCT_TYPES,
                         validity_types=VALIDITY_TYPES)


@orders_bp.route('/api/orders')
@login_required
def get_orders():
    """Get all orders (order book)"""
    try:
        if not current_user.kite_access_token:
            return jsonify({'success': False, 'error': 'Kite not connected'}), 401

        kite = KiteConnect(api_key=current_user.kite_api_key)
        kite.set_access_token(current_user.kite_access_token)

        # Fetch orders
        orders = kite.orders()

        return jsonify({
            'success': True,
            'orders': orders,
            'count': len(orders)
        })

    except Exception as e:
        logging.error(f"Error fetching orders: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@orders_bp.route('/api/orders/<order_id>')
@login_required
def get_order_details(order_id):
    """Get order details and history"""
    try:
        if not current_user.kite_access_token:
            return jsonify({'success': False, 'error': 'Kite not connected'}), 401

        kite = KiteConnect(api_key=current_user.kite_api_key)
        kite.set_access_token(current_user.kite_access_token)

        # Fetch order history
        order_history = kite.order_history(order_id)

        return jsonify({
            'success': True,
            'order_history': order_history
        })

    except Exception as e:
        logging.error(f"Error fetching order details: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@orders_bp.route('/api/place', methods=['POST'])
@login_required
def place_order():
    """Place a new order"""
    try:
        if not current_user.kite_access_token:
            return jsonify({'success': False, 'error': 'Kite not connected'}), 401

        data = request.json if request.is_json else request.form

        # Validate required fields
        required_fields = ['tradingsymbol', 'exchange', 'transaction_type',
                          'quantity', 'order_type', 'product']

        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        kite = KiteConnect(api_key=current_user.kite_api_key)
        kite.set_access_token(current_user.kite_access_token)

        # Prepare order parameters
        order_params = {
            'tradingsymbol': data.get('tradingsymbol'),
            'exchange': data.get('exchange'),
            'transaction_type': data.get('transaction_type'),
            'quantity': int(data.get('quantity')),
            'order_type': data.get('order_type'),
            'product': data.get('product'),
            'validity': data.get('validity', 'DAY')
        }

        # Add price for limit orders
        if order_params['order_type'] in ['LIMIT', 'SL']:
            price = data.get('price')
            if not price:
                return jsonify({
                    'success': False,
                    'error': 'Price is required for limit/SL orders'
                }), 400
            order_params['price'] = float(price)

        # Add trigger price for SL orders
        if order_params['order_type'] in ['SL', 'SL-M']:
            trigger_price = data.get('trigger_price')
            if not trigger_price:
                return jsonify({
                    'success': False,
                    'error': 'Trigger price is required for SL orders'
                }), 400
            order_params['trigger_price'] = float(trigger_price)

        # Place order
        order_id = kite.place_order(variety=kite.VARIETY_REGULAR, **order_params)

        logging.info(f"Order placed successfully: {order_id}")

        return jsonify({
            'success': True,
            'order_id': order_id,
            'message': f'Order placed successfully (ID: {order_id})'
        })

    except Exception as e:
        logging.error(f"Error placing order: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@orders_bp.route('/api/modify/<order_id>', methods=['POST'])
@login_required
def modify_order(order_id):
    """Modify an existing order"""
    try:
        if not current_user.kite_access_token:
            return jsonify({'success': False, 'error': 'Kite not connected'}), 401

        data = request.json if request.is_json else request.form

        kite = KiteConnect(api_key=current_user.kite_api_key)
        kite.set_access_token(current_user.kite_access_token)

        # Prepare modification parameters
        modify_params = {}

        if data.get('quantity'):
            modify_params['quantity'] = int(data.get('quantity'))

        if data.get('price'):
            modify_params['price'] = float(data.get('price'))

        if data.get('trigger_price'):
            modify_params['trigger_price'] = float(data.get('trigger_price'))

        if data.get('order_type'):
            modify_params['order_type'] = data.get('order_type')

        if not modify_params:
            return jsonify({
                'success': False,
                'error': 'No modification parameters provided'
            }), 400

        # Modify order
        kite.modify_order(variety=kite.VARIETY_REGULAR,
                         order_id=order_id,
                         **modify_params)

        logging.info(f"Order modified successfully: {order_id}")

        return jsonify({
            'success': True,
            'message': f'Order {order_id} modified successfully'
        })

    except Exception as e:
        logging.error(f"Error modifying order: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@orders_bp.route('/api/cancel/<order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    """Cancel an existing order"""
    try:
        if not current_user.kite_access_token:
            return jsonify({'success': False, 'error': 'Kite not connected'}), 401

        kite = KiteConnect(api_key=current_user.kite_api_key)
        kite.set_access_token(current_user.kite_access_token)

        # Cancel order
        kite.cancel_order(variety=kite.VARIETY_REGULAR, order_id=order_id)

        logging.info(f"Order cancelled successfully: {order_id}")

        return jsonify({
            'success': True,
            'message': f'Order {order_id} cancelled successfully'
        })

    except Exception as e:
        logging.error(f"Error cancelling order: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@orders_bp.route('/api/trades')
@login_required
def get_trades():
    """Get all trades (executed orders)"""
    try:
        if not current_user.kite_access_token:
            return jsonify({'success': False, 'error': 'Kite not connected'}), 401

        kite = KiteConnect(api_key=current_user.kite_api_key)
        kite.set_access_token(current_user.kite_access_token)

        # Fetch trades
        trades = kite.trades()

        return jsonify({
            'success': True,
            'trades': trades,
            'count': len(trades)
        })

    except Exception as e:
        logging.error(f"Error fetching trades: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
