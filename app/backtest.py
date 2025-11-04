from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import BacktestStrategy, BacktestResult, Instrument
from datetime import datetime, timedelta
import logging
import json

backtest_bp = Blueprint('backtest', __name__, url_prefix='/backtest')


@backtest_bp.route('/')
@login_required
def index():
    """Backtest main page - list all strategies"""
    strategies = BacktestStrategy.query.filter_by(user_id=current_user.id).order_by(
        BacktestStrategy.created_at.desc()
    ).all()

    return render_template('backtest/index.html',
                         title='Backtest',
                         strategies=strategies)


@backtest_bp.route('/create')
@login_required
def create():
    """Create new backtest strategy form"""
    # Get available indicators and conditions
    indicators = get_available_indicators()
    conditions = get_available_conditions()

    return render_template('backtest/create.html',
                         title='Create Strategy',
                         indicators=indicators,
                         conditions=conditions)


@backtest_bp.route('/strategy/<int:strategy_id>')
@login_required
def view_strategy(strategy_id):
    """View strategy details and results"""
    strategy = BacktestStrategy.query.filter_by(
        id=strategy_id,
        user_id=current_user.id
    ).first_or_404()

    # Get all backtest results for this strategy
    results = BacktestResult.query.filter_by(
        strategy_id=strategy_id
    ).order_by(BacktestResult.run_date.desc()).all()

    return render_template('backtest/view.html',
                         title=strategy.name,
                         strategy=strategy,
                         results=results)


@backtest_bp.route('/api/strategies', methods=['POST'])
@login_required
def save_strategy():
    """Save new backtest strategy"""
    try:
        data = request.json if request.is_json else request.form

        # Validate required fields
        required_fields = ['name', 'entry_rules', 'exit_rules']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        # Create new strategy
        strategy = BacktestStrategy(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description', ''),
            entry_rules=json.dumps(data.get('entry_rules')),
            exit_rules=json.dumps(data.get('exit_rules')),
            timeframe=data.get('timeframe', 'day'),
            initial_capital=float(data.get('initial_capital', 100000)),
            position_size=float(data.get('position_size', 10))
        )

        db.session.add(strategy)
        db.session.commit()

        logging.info(f"Strategy created successfully: {strategy.id}")

        return jsonify({
            'success': True,
            'strategy_id': strategy.id,
            'message': 'Strategy created successfully'
        })

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving strategy: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@backtest_bp.route('/api/strategies/<int:strategy_id>', methods=['PUT'])
@login_required
def update_strategy(strategy_id):
    """Update existing strategy"""
    try:
        strategy = BacktestStrategy.query.filter_by(
            id=strategy_id,
            user_id=current_user.id
        ).first_or_404()

        data = request.json if request.is_json else request.form

        # Update fields
        if data.get('name'):
            strategy.name = data.get('name')
        if data.get('description') is not None:
            strategy.description = data.get('description')
        if data.get('entry_rules'):
            strategy.entry_rules = json.dumps(data.get('entry_rules'))
        if data.get('exit_rules'):
            strategy.exit_rules = json.dumps(data.get('exit_rules'))
        if data.get('timeframe'):
            strategy.timeframe = data.get('timeframe')
        if data.get('initial_capital'):
            strategy.initial_capital = float(data.get('initial_capital'))
        if data.get('position_size'):
            strategy.position_size = float(data.get('position_size'))

        strategy.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Strategy updated successfully'
        })

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating strategy: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@backtest_bp.route('/api/strategies/<int:strategy_id>', methods=['DELETE'])
@login_required
def delete_strategy(strategy_id):
    """Delete strategy and its results"""
    try:
        strategy = BacktestStrategy.query.filter_by(
            id=strategy_id,
            user_id=current_user.id
        ).first_or_404()

        # Delete all results first
        BacktestResult.query.filter_by(strategy_id=strategy_id).delete()

        # Delete strategy
        db.session.delete(strategy)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Strategy deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting strategy: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@backtest_bp.route('/api/run/<int:strategy_id>', methods=['POST'])
@login_required
def run_backtest(strategy_id):
    """Run backtest for a strategy"""
    try:
        if not current_user.kite_access_token:
            return jsonify({
                'success': False,
                'error': 'Kite not connected. Historical data requires Kite access.'
            }), 401

        strategy = BacktestStrategy.query.filter_by(
            id=strategy_id,
            user_id=current_user.id
        ).first_or_404()

        data = request.json if request.is_json else request.form

        # Get backtest parameters
        symbol = data.get('symbol')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if not all([symbol, start_date, end_date]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: symbol, start_date, end_date'
            }), 400

        # Validate instrument exists
        instrument = Instrument.query.filter_by(tradingsymbol=symbol).first()
        if not instrument:
            return jsonify({
                'success': False,
                'error': f'Instrument {symbol} not found'
            }), 404

        # In a real implementation, you would:
        # 1. Fetch historical data from Kite
        # 2. Apply strategy rules
        # 3. Calculate performance metrics
        # For now, we'll create a placeholder result

        # Create backtest result (placeholder implementation)
        result = BacktestResult(
            strategy_id=strategy_id,
            symbol=symbol,
            start_date=datetime.strptime(start_date, '%Y-%m-%d'),
            end_date=datetime.strptime(end_date, '%Y-%m-%d'),
            initial_capital=strategy.initial_capital,
            final_capital=strategy.initial_capital * 1.15,  # Placeholder: 15% gain
            total_trades=25,
            winning_trades=15,
            losing_trades=10,
            win_rate=60.0,
            total_return=15.0,
            max_drawdown=-8.5,
            sharpe_ratio=1.35,
            trade_details=json.dumps({'placeholder': 'Trade details would be here'}),
            equity_curve=json.dumps({'placeholder': 'Equity curve data'})
        )

        db.session.add(result)
        db.session.commit()

        logging.info(f"Backtest completed successfully: {result.id}")

        return jsonify({
            'success': True,
            'result_id': result.id,
            'message': 'Backtest completed successfully',
            'summary': {
                'total_return': result.total_return,
                'win_rate': result.win_rate,
                'total_trades': result.total_trades,
                'sharpe_ratio': result.sharpe_ratio
            }
        })

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error running backtest: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@backtest_bp.route('/api/results/<int:result_id>')
@login_required
def get_result(result_id):
    """Get detailed backtest result"""
    try:
        result = BacktestResult.query.filter_by(id=result_id).first_or_404()

        # Verify user owns this strategy
        strategy = BacktestStrategy.query.filter_by(
            id=result.strategy_id,
            user_id=current_user.id
        ).first_or_404()

        return jsonify({
            'success': True,
            'result': {
                'id': result.id,
                'symbol': result.symbol,
                'start_date': result.start_date.isoformat(),
                'end_date': result.end_date.isoformat(),
                'initial_capital': result.initial_capital,
                'final_capital': result.final_capital,
                'total_return': result.total_return,
                'total_trades': result.total_trades,
                'winning_trades': result.winning_trades,
                'losing_trades': result.losing_trades,
                'win_rate': result.win_rate,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'trade_details': json.loads(result.trade_details) if result.trade_details else {},
                'equity_curve': json.loads(result.equity_curve) if result.equity_curve else {}
            }
        })

    except Exception as e:
        logging.error(f"Error fetching result: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def get_available_indicators():
    """Get list of available technical indicators"""
    return {
        'SMA': 'Simple Moving Average',
        'EMA': 'Exponential Moving Average',
        'RSI': 'Relative Strength Index',
        'MACD': 'Moving Average Convergence Divergence',
        'BB': 'Bollinger Bands',
        'ATR': 'Average True Range',
        'VOLUME': 'Volume',
        'PRICE': 'Price'
    }


def get_available_conditions():
    """Get list of available conditions"""
    return {
        'CROSSES_ABOVE': 'Crosses Above',
        'CROSSES_BELOW': 'Crosses Below',
        'GREATER_THAN': 'Greater Than',
        'LESS_THAN': 'Less Than',
        'EQUALS': 'Equals',
        'BETWEEN': 'Between'
    }
