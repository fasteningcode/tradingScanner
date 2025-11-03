from datetime import datetime
from flask import current_app
from app import db
from app.models import Order, Position, Instrument
from app.kite_auth import get_kite_client


class TradingService:
    """
    Service for managing trading operations via Kite Connect
    Handles order placement, modification, cancellation, and position management
    """

    def __init__(self, user):
        """
        Initialize TradingService

        Args:
            user: User model instance
        """
        self.user = user
        self.kite = get_kite_client()

    def place_order(self, tradingsymbol, exchange, transaction_type, quantity,
                    order_type='MARKET', product='CNC', price=None, trigger_price=None,
                    variety='regular', validity='DAY', disclosed_quantity=None, tag=None):
        """
        Place an order

        Args:
            tradingsymbol: Trading symbol (e.g., 'RELIANCE', 'INFY')
            exchange: Exchange (NSE, BSE, NFO, etc.)
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: Order type (MARKET, LIMIT, SL, SL-M)
            product: Product type (CNC, MIS, NRML)
            price: Limit price (required for LIMIT orders)
            trigger_price: Trigger price (required for SL, SL-M orders)
            variety: Order variety (regular, amo, co, iceberg)
            validity: Order validity (DAY, IOC)
            disclosed_quantity: Disclosed quantity for iceberg orders
            tag: Custom tag for order tracking

        Returns:
            dict: Order response with order_id
        """
        try:
            # Validate token
            if not self.user.is_kite_token_valid():
                raise ValueError('Kite access token expired. Please reconnect.')

            # Find instrument
            instrument = Instrument.query.filter_by(
                tradingsymbol=tradingsymbol,
                exchange=exchange
            ).first()

            if not instrument:
                raise ValueError(f'Instrument {tradingsymbol} not found on {exchange}')

            # Place order via Kite API
            order_params = {
                'tradingsymbol': tradingsymbol,
                'exchange': exchange,
                'transaction_type': transaction_type,
                'quantity': quantity,
                'order_type': order_type,
                'product': product,
                'variety': variety,
                'validity': validity
            }

            if price is not None:
                order_params['price'] = price

            if trigger_price is not None:
                order_params['trigger_price'] = trigger_price

            if disclosed_quantity is not None:
                order_params['disclosed_quantity'] = disclosed_quantity

            if tag:
                order_params['tag'] = tag

            # Execute order placement
            order_response = self.kite.place_order(**order_params)
            order_id = order_response.get('order_id')

            if not order_id:
                raise ValueError('Order placement failed: No order ID returned')

            # Fetch order details
            order_details = self.kite.order_history(order_id)[-1]  # Get latest status

            # Store order in database
            order = Order(
                user_id=self.user.id,
                instrument_id=instrument.id,
                order_id=order_id,
                exchange_order_id=order_details.get('exchange_order_id'),
                parent_order_id=order_details.get('parent_order_id'),
                transaction_type=transaction_type,
                order_type=order_type,
                product=product,
                variety=variety,
                quantity=quantity,
                price=price or 0.0,
                trigger_price=trigger_price or 0.0,
                disclosed_quantity=disclosed_quantity or 0,
                status=order_details.get('status', 'OPEN'),
                status_message=order_details.get('status_message'),
                filled_quantity=order_details.get('filled_quantity', 0),
                pending_quantity=order_details.get('pending_quantity', quantity),
                average_price=order_details.get('average_price', 0.0),
                order_timestamp=order_details.get('order_timestamp', datetime.utcnow()),
                exchange_timestamp=order_details.get('exchange_timestamp')
            )

            db.session.add(order)
            db.session.commit()

            current_app.logger.info(f'Order placed: {order_id} - {transaction_type} {quantity} {tradingsymbol}')

            return {
                'order_id': order_id,
                'status': order_details.get('status'),
                'message': f'Order placed successfully: {transaction_type} {quantity} {tradingsymbol}'
            }

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error placing order: {str(e)}')
            raise

    def modify_order(self, order_id, quantity=None, price=None, order_type=None, trigger_price=None, validity=None):
        """
        Modify an existing order

        Args:
            order_id: Order ID to modify
            quantity: New quantity
            price: New limit price
            order_type: New order type
            trigger_price: New trigger price
            validity: New validity

        Returns:
            dict: Modified order response
        """
        try:
            # Validate token
            if not self.user.is_kite_token_valid():
                raise ValueError('Kite access token expired. Please reconnect.')

            # Get order from database
            order = Order.query.filter_by(
                order_id=order_id,
                user_id=self.user.id
            ).first()

            if not order:
                raise ValueError(f'Order {order_id} not found')

            # Build modification params
            modify_params = {
                'order_id': order_id,
                'variety': order.variety
            }

            if quantity is not None:
                modify_params['quantity'] = quantity

            if price is not None:
                modify_params['price'] = price

            if order_type is not None:
                modify_params['order_type'] = order_type

            if trigger_price is not None:
                modify_params['trigger_price'] = trigger_price

            if validity is not None:
                modify_params['validity'] = validity

            # Execute modification
            modify_response = self.kite.modify_order(**modify_params)

            # Update order in database
            if quantity is not None:
                order.quantity = quantity
                order.pending_quantity = quantity - order.filled_quantity

            if price is not None:
                order.price = price

            if order_type is not None:
                order.order_type = order_type

            if trigger_price is not None:
                order.trigger_price = trigger_price

            order.updated_at = datetime.utcnow()
            db.session.commit()

            current_app.logger.info(f'Order modified: {order_id}')

            return {
                'order_id': order_id,
                'status': 'modified',
                'message': f'Order {order_id} modified successfully'
            }

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error modifying order: {str(e)}')
            raise

    def cancel_order(self, order_id, variety='regular'):
        """
        Cancel an order

        Args:
            order_id: Order ID to cancel
            variety: Order variety

        Returns:
            dict: Cancellation response
        """
        try:
            # Validate token
            if not self.user.is_kite_token_valid():
                raise ValueError('Kite access token expired. Please reconnect.')

            # Get order from database
            order = Order.query.filter_by(
                order_id=order_id,
                user_id=self.user.id
            ).first()

            if not order:
                raise ValueError(f'Order {order_id} not found')

            # Execute cancellation
            cancel_response = self.kite.cancel_order(
                variety=variety or order.variety,
                order_id=order_id
            )

            # Update order status
            order.status = 'CANCELLED'
            order.updated_at = datetime.utcnow()
            db.session.commit()

            current_app.logger.info(f'Order cancelled: {order_id}')

            return {
                'order_id': order_id,
                'status': 'cancelled',
                'message': f'Order {order_id} cancelled successfully'
            }

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error cancelling order: {str(e)}')
            raise

    def get_orders(self):
        """
        Get all orders for the user

        Returns:
            list: List of orders from Kite API
        """
        try:
            # Validate token
            if not self.user.is_kite_token_valid():
                raise ValueError('Kite access token expired. Please reconnect.')

            orders = self.kite.orders()
            return orders

        except Exception as e:
            current_app.logger.error(f'Error fetching orders: {str(e)}')
            raise

    def get_order_history(self, order_id):
        """
        Get order history/status updates

        Args:
            order_id: Order ID

        Returns:
            list: Order history
        """
        try:
            # Validate token
            if not self.user.is_kite_token_valid():
                raise ValueError('Kite access token expired. Please reconnect.')

            history = self.kite.order_history(order_id)
            return history

        except Exception as e:
            current_app.logger.error(f'Error fetching order history: {str(e)}')
            raise

    def sync_orders(self):
        """
        Sync orders from Kite API to database

        Returns:
            dict: Sync statistics
        """
        try:
            # Validate token
            if not self.user.is_kite_token_valid():
                raise ValueError('Kite access token expired. Please reconnect.')

            # Fetch orders from Kite
            kite_orders = self.kite.orders()

            created_count = 0
            updated_count = 0

            for kite_order in kite_orders:
                order_id = kite_order.get('order_id')

                # Find instrument
                tradingsymbol = kite_order.get('tradingsymbol')
                exchange = kite_order.get('exchange')

                instrument = Instrument.query.filter_by(
                    tradingsymbol=tradingsymbol,
                    exchange=exchange
                ).first()

                if not instrument:
                    continue

                # Check if order exists in database
                order = Order.query.filter_by(order_id=order_id).first()

                if order:
                    # Update existing order
                    order.status = kite_order.get('status')
                    order.status_message = kite_order.get('status_message')
                    order.filled_quantity = kite_order.get('filled_quantity', 0)
                    order.pending_quantity = kite_order.get('pending_quantity', 0)
                    order.average_price = kite_order.get('average_price', 0.0)
                    order.updated_at = datetime.utcnow()
                    updated_count += 1

                else:
                    # Create new order
                    order = Order(
                        user_id=self.user.id,
                        instrument_id=instrument.id,
                        order_id=order_id,
                        exchange_order_id=kite_order.get('exchange_order_id'),
                        parent_order_id=kite_order.get('parent_order_id'),
                        transaction_type=kite_order.get('transaction_type'),
                        order_type=kite_order.get('order_type'),
                        product=kite_order.get('product'),
                        variety=kite_order.get('variety'),
                        quantity=kite_order.get('quantity'),
                        price=kite_order.get('price', 0.0),
                        trigger_price=kite_order.get('trigger_price', 0.0),
                        disclosed_quantity=kite_order.get('disclosed_quantity', 0),
                        status=kite_order.get('status'),
                        status_message=kite_order.get('status_message'),
                        filled_quantity=kite_order.get('filled_quantity', 0),
                        pending_quantity=kite_order.get('pending_quantity', 0),
                        average_price=kite_order.get('average_price', 0.0),
                        order_timestamp=kite_order.get('order_timestamp', datetime.utcnow()),
                        exchange_timestamp=kite_order.get('exchange_timestamp')
                    )
                    db.session.add(order)
                    created_count += 1

            db.session.commit()

            stats = {
                'created': created_count,
                'updated': updated_count,
                'total': len(kite_orders)
            }

            current_app.logger.info(f'Orders synced: {stats}')
            return stats

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error syncing orders: {str(e)}')
            raise

    def get_positions(self):
        """
        Get current positions

        Returns:
            dict: Positions (net and day)
        """
        try:
            # Validate token
            if not self.user.is_kite_token_valid():
                raise ValueError('Kite access token expired. Please reconnect.')

            positions = self.kite.positions()
            return positions

        except Exception as e:
            current_app.logger.error(f'Error fetching positions: {str(e)}')
            raise

    def sync_positions(self):
        """
        Sync positions from Kite API to database

        Returns:
            dict: Sync statistics
        """
        try:
            # Validate token
            if not self.user.is_kite_token_valid():
                raise ValueError('Kite access token expired. Please reconnect.')

            # Fetch positions
            positions_data = self.kite.positions()
            net_positions = positions_data.get('net', [])

            # Clear existing positions
            Position.query.filter_by(user_id=self.user.id).delete()

            created_count = 0

            for pos_data in net_positions:
                # Skip positions with zero quantity
                if pos_data.get('quantity', 0) == 0:
                    continue

                # Find instrument
                tradingsymbol = pos_data.get('tradingsymbol')
                exchange = pos_data.get('exchange')

                instrument = Instrument.query.filter_by(
                    tradingsymbol=tradingsymbol,
                    exchange=exchange
                ).first()

                if not instrument:
                    continue

                # Create position
                position = Position(
                    user_id=self.user.id,
                    instrument_id=instrument.id,
                    product=pos_data.get('product'),
                    quantity=pos_data.get('quantity'),
                    overnight_quantity=pos_data.get('overnight_quantity', 0),
                    multiplier=pos_data.get('multiplier', 1.0),
                    average_price=pos_data.get('average_price', 0.0),
                    buy_price=pos_data.get('buy_price', 0.0),
                    sell_price=pos_data.get('sell_price', 0.0),
                    buy_quantity=pos_data.get('buy_quantity', 0),
                    sell_quantity=pos_data.get('sell_quantity', 0),
                    buy_value=pos_data.get('buy_value', 0.0),
                    sell_value=pos_data.get('sell_value', 0.0),
                    pnl=pos_data.get('pnl', 0.0),
                    realised=pos_data.get('realised', 0.0),
                    unrealised=pos_data.get('unrealised', 0.0)
                )
                db.session.add(position)
                created_count += 1

            db.session.commit()

            stats = {
                'created': created_count,
                'total': len(net_positions)
            }

            current_app.logger.info(f'Positions synced: {stats}')
            return stats

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error syncing positions: {str(e)}')
            raise

    def get_holdings(self):
        """
        Get holdings (long-term positions)

        Returns:
            list: Holdings data
        """
        try:
            # Validate token
            if not self.user.is_kite_token_valid():
                raise ValueError('Kite access token expired. Please reconnect.')

            holdings = self.kite.holdings()
            return holdings

        except Exception as e:
            current_app.logger.error(f'Error fetching holdings: {str(e)}')
            raise
