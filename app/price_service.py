"""
Stock Price Service

This module provides functions to fetch and calculate stock prices with percentage changes
from historical candlestick data.
"""

from typing import Dict, List, Optional
from flask import current_app
from app.models import HistoricalData


def get_stock_prices_with_changes(tradingsymbols: List[str], interval: str = 'day') -> Dict[str, Dict]:
    """
    Get latest prices and percentage changes for a list of stocks

    Args:
        tradingsymbols: List of trading symbols to fetch prices for
        interval: Candle interval (default: 'day')

    Returns:
        Dictionary mapping tradingsymbol to price data:
        {
            'RELIANCE': {
                'last_price': 2450.50,
                'percentage_change': 2.35,
                'change_direction': 'up',  # 'up', 'down', or 'neutral'
                'previous_close': 2394.25
            },
            ...
        }
    """
    price_data = {}

    if not tradingsymbols:
        return price_data

    try:
        # Fetch historical data for all symbols in one query
        historical_records = HistoricalData.query.filter(
            HistoricalData.tradingsymbol.in_(tradingsymbols),
            HistoricalData.interval == interval
        ).all()

        # Create a mapping of tradingsymbol to historical data
        hist_data_map = {record.tradingsymbol: record for record in historical_records}

        # Process each symbol
        for symbol in tradingsymbols:
            price_info = _calculate_price_change(symbol, hist_data_map.get(symbol))
            price_data[symbol] = price_info

    except Exception as e:
        current_app.logger.error(f'Error fetching stock prices: {str(e)}')
        # Return empty data for all symbols on error
        for symbol in tradingsymbols:
            price_data[symbol] = {
                'last_price': 0.0,
                'percentage_change': 0.0,
                'change_direction': 'neutral',
                'previous_close': 0.0
            }

    return price_data


def _calculate_price_change(tradingsymbol: str, historical_data: Optional[HistoricalData]) -> Dict:
    """
    Calculate price change for a single stock

    Args:
        tradingsymbol: Trading symbol
        historical_data: HistoricalData record or None

    Returns:
        Dictionary with price information
    """
    default_result = {
        'last_price': 0.0,
        'percentage_change': 0.0,
        'change_direction': 'neutral',
        'previous_close': 0.0
    }

    try:
        if not historical_data:
            return default_result

        # Get candles from JSON data
        candles = historical_data.get_candles()

        if not candles or len(candles) == 0:
            return default_result

        # Get latest candle (most recent day)
        latest_candle = candles[-1]
        latest_close = float(latest_candle.get('close', 0))

        if latest_close <= 0:
            return default_result

        # If we have at least 2 candles, calculate percentage change
        if len(candles) >= 2:
            previous_candle = candles[-2]
            previous_close = float(previous_candle.get('close', 0))

            if previous_close > 0:
                percentage_change = ((latest_close - previous_close) / previous_close) * 100

                # Determine change direction
                if percentage_change > 0:
                    change_direction = 'up'
                elif percentage_change < 0:
                    change_direction = 'down'
                else:
                    change_direction = 'neutral'

                return {
                    'last_price': latest_close,
                    'percentage_change': percentage_change,
                    'change_direction': change_direction,
                    'previous_close': previous_close
                }

        # Only one candle available - show price but no change
        return {
            'last_price': latest_close,
            'percentage_change': 0.0,
            'change_direction': 'neutral',
            'previous_close': latest_close
        }

    except Exception as e:
        current_app.logger.error(
            f'Error calculating price change for {tradingsymbol}: {str(e)}'
        )
        return default_result


def get_single_stock_price(tradingsymbol: str, interval: str = 'day') -> Dict:
    """
    Get price information for a single stock

    Args:
        tradingsymbol: Trading symbol
        interval: Candle interval (default: 'day')

    Returns:
        Dictionary with price information
    """
    result = get_stock_prices_with_changes([tradingsymbol], interval)
    return result.get(tradingsymbol, {
        'last_price': 0.0,
        'percentage_change': 0.0,
        'change_direction': 'neutral',
        'previous_close': 0.0
    })
