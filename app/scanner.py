import json
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from flask import current_app
from app import db
from app.models import Instrument, ScanResult, ScannerStrategy
from app.market_data import MarketDataService
from app.kite_auth import get_kite_client


class StockScanner:
    """
    Stock scanner service for identifying trading opportunities
    Implements various scanning strategies
    """

    def __init__(self, user):
        """
        Initialize StockScanner

        Args:
            user: User model instance
        """
        self.user = user
        self.kite = get_kite_client()

    def scan_volume_breakout(self, exchange='NSE', volume_multiplier=2.0, min_price=10.0, max_price=5000.0):
        """
        Scan for stocks with volume breakout
        Identifies stocks where current volume is significantly higher than average

        Args:
            exchange: Exchange to scan (NSE, BSE)
            volume_multiplier: Minimum volume multiplier vs average (default: 2x)
            min_price: Minimum stock price filter
            max_price: Maximum stock price filter

        Returns:
            list: List of scan results
        """
        try:
            # Get equity instruments
            instruments = Instrument.query.filter_by(
                exchange=exchange,
                instrument_type='EQ'
            ).filter(
                Instrument.last_price >= min_price,
                Instrument.last_price <= max_price
            ).limit(500).all()

            current_app.logger.info(f'Scanning {len(instruments)} instruments for volume breakout')

            results = []
            instrument_tokens = [inst.instrument_token for inst in instruments]

            # Fetch quotes in batches (Kite API limit is ~500 instruments per call)
            batch_size = 200
            for i in range(0, len(instrument_tokens), batch_size):
                batch_tokens = instrument_tokens[i:i+batch_size]

                try:
                    quotes = MarketDataService.get_quotes(batch_tokens)

                    for inst in instruments[i:i+batch_size]:
                        try:
                            quote_key = f'{inst.exchange}:{inst.instrument_token}'
                            if quote_key not in quotes:
                                continue

                            quote = quotes[quote_key]
                            current_volume = quote.get('volume', 0)
                            average_volume = quote.get('average_price', 0)  # Using average_price as proxy
                            last_price = quote.get('last_price', 0)

                            # Simple volume check (in production, use historical average)
                            if current_volume > 0 and last_price >= min_price and last_price <= max_price:
                                # Calculate volume ratio
                                # Note: For accurate volume breakout, fetch historical data for average volume
                                ohlc = quote.get('ohlc', {})

                                scan_data = {
                                    'last_price': last_price,
                                    'volume': current_volume,
                                    'change_percent': quote.get('net_change', 0),
                                    'open': ohlc.get('open', 0),
                                    'high': ohlc.get('high', 0),
                                    'low': ohlc.get('low', 0),
                                    'close': ohlc.get('close', 0)
                                }

                                results.append({
                                    'instrument': inst,
                                    'scan_data': scan_data,
                                    'signal_strength': min(current_volume / 1000000, 10.0)  # Normalized signal
                                })

                        except Exception as e:
                            current_app.logger.warning(f'Error processing instrument {inst.tradingsymbol}: {str(e)}')
                            continue

                except Exception as e:
                    current_app.logger.error(f'Error fetching quotes for batch: {str(e)}')
                    continue

            # Sort by volume
            results.sort(key=lambda x: x['scan_data'].get('volume', 0), reverse=True)

            current_app.logger.info(f'Volume breakout scan found {len(results)} results')
            return results[:50]  # Return top 50

        except Exception as e:
            current_app.logger.error(f'Error in volume breakout scan: {str(e)}')
            raise

    def scan_price_breakout(self, exchange='NSE', period_days=52, min_price=10.0, max_price=5000.0):
        """
        Scan for stocks breaking out to new highs

        Args:
            exchange: Exchange to scan (NSE, BSE)
            period_days: Period for high calculation (default: 52 weeks = 260 days)
            min_price: Minimum stock price filter
            max_price: Maximum stock price filter

        Returns:
            list: List of scan results
        """
        try:
            # Get equity instruments
            instruments = Instrument.query.filter_by(
                exchange=exchange,
                instrument_type='EQ'
            ).filter(
                Instrument.last_price >= min_price,
                Instrument.last_price <= max_price
            ).limit(100).all()  # Limit for historical data API calls

            current_app.logger.info(f'Scanning {len(instruments)} instruments for price breakout')

            results = []
            to_date = datetime.now()
            from_date = to_date - timedelta(days=period_days * 7 // 5)  # Adjust for weekends

            for inst in instruments:
                try:
                    # Fetch historical data
                    historical = MarketDataService.get_historical_data(
                        instrument_token=inst.instrument_token,
                        from_date=from_date,
                        to_date=to_date,
                        interval='day'
                    )

                    if not historical or len(historical) < 10:
                        continue

                    # Convert to DataFrame for analysis
                    df = pd.DataFrame(historical)

                    # Find highest high in the period
                    period_high = df['high'].max()
                    current_price = df.iloc[-1]['close']

                    # Check if current price is breaking out (within 2% of period high)
                    if current_price >= period_high * 0.98:
                        price_change_percent = ((current_price - df.iloc[0]['close']) / df.iloc[0]['close']) * 100

                        scan_data = {
                            'last_price': current_price,
                            'period_high': period_high,
                            'breakout_percent': ((current_price / period_high) - 1) * 100,
                            'price_change_percent': price_change_percent,
                            'volume': df.iloc[-1]['volume'],
                            'period_days': period_days
                        }

                        signal_strength = min(abs(price_change_percent) / 10, 10.0)

                        results.append({
                            'instrument': inst,
                            'scan_data': scan_data,
                            'signal_strength': signal_strength
                        })

                except Exception as e:
                    current_app.logger.warning(f'Error processing {inst.tradingsymbol}: {str(e)}')
                    continue

            # Sort by breakout strength
            results.sort(key=lambda x: x['signal_strength'], reverse=True)

            current_app.logger.info(f'Price breakout scan found {len(results)} results')
            return results[:30]  # Return top 30

        except Exception as e:
            current_app.logger.error(f'Error in price breakout scan: {str(e)}')
            raise

    def scan_rsi(self, exchange='NSE', period=14, oversold=30, overbought=70, min_price=10.0, max_price=5000.0):
        """
        Scan for stocks based on RSI indicator

        Args:
            exchange: Exchange to scan (NSE, BSE)
            period: RSI period (default: 14)
            oversold: Oversold threshold (default: 30)
            overbought: Overbought threshold (default: 70)
            min_price: Minimum stock price filter
            max_price: Maximum stock price filter

        Returns:
            list: List of scan results with RSI
        """
        try:
            # Get equity instruments
            instruments = Instrument.query.filter_by(
                exchange=exchange,
                instrument_type='EQ'
            ).filter(
                Instrument.last_price >= min_price,
                Instrument.last_price <= max_price
            ).limit(100).all()

            current_app.logger.info(f'Scanning {len(instruments)} instruments for RSI')

            results = []
            to_date = datetime.now()
            from_date = to_date - timedelta(days=60)  # 60 days for RSI calculation

            for inst in instruments:
                try:
                    # Fetch historical data
                    historical = MarketDataService.get_historical_data(
                        instrument_token=inst.instrument_token,
                        from_date=from_date,
                        to_date=to_date,
                        interval='day'
                    )

                    if not historical or len(historical) < period + 1:
                        continue

                    # Convert to DataFrame
                    df = pd.DataFrame(historical)

                    # Calculate RSI
                    rsi = self.calculate_rsi(df['close'], period)
                    current_rsi = rsi.iloc[-1]

                    # Check for oversold or overbought conditions
                    if current_rsi <= oversold or current_rsi >= overbought:
                        signal_type = 'oversold' if current_rsi <= oversold else 'overbought'

                        scan_data = {
                            'last_price': df.iloc[-1]['close'],
                            'rsi': current_rsi,
                            'signal_type': signal_type,
                            'volume': df.iloc[-1]['volume'],
                            'change_percent': ((df.iloc[-1]['close'] - df.iloc[-2]['close']) / df.iloc[-2]['close']) * 100
                        }

                        # Signal strength based on how extreme the RSI is
                        if signal_type == 'oversold':
                            signal_strength = min((oversold - current_rsi) / 10, 10.0)
                        else:
                            signal_strength = min((current_rsi - overbought) / 10, 10.0)

                        results.append({
                            'instrument': inst,
                            'scan_data': scan_data,
                            'signal_strength': signal_strength
                        })

                except Exception as e:
                    current_app.logger.warning(f'Error processing {inst.tradingsymbol}: {str(e)}')
                    continue

            # Sort by signal strength
            results.sort(key=lambda x: x['signal_strength'], reverse=True)

            current_app.logger.info(f'RSI scan found {len(results)} results')
            return results[:30]  # Return top 30

        except Exception as e:
            current_app.logger.error(f'Error in RSI scan: {str(e)}')
            raise

    @staticmethod
    def calculate_rsi(prices, period=14):
        """
        Calculate RSI indicator

        Args:
            prices: Pandas Series of closing prices
            period: RSI period

        Returns:
            Pandas Series: RSI values
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def save_scan_results(self, strategy_name, results):
        """
        Save scan results to database

        Args:
            strategy_name: Name of the scanner strategy
            results: List of scan results

        Returns:
            int: Number of results saved
        """
        try:
            # Get or create strategy
            strategy = ScannerStrategy.query.filter_by(name=strategy_name).first()
            if not strategy:
                strategy = ScannerStrategy(
                    name=strategy_name,
                    strategy_type=strategy_name.lower().replace(' ', '_')
                )
                db.session.add(strategy)
                db.session.commit()

            # Clear old results for this strategy (older than 1 day)
            cutoff = datetime.utcnow() - timedelta(days=1)
            ScanResult.query.filter(
                ScanResult.user_id == self.user.id,
                ScanResult.strategy_id == strategy.id,
                ScanResult.scan_timestamp < cutoff
            ).delete()

            # Save new results
            saved_count = 0
            for result in results:
                instrument = result['instrument']
                scan_data = result['scan_data']
                signal_strength = result['signal_strength']

                scan_result = ScanResult(
                    user_id=self.user.id,
                    strategy_id=strategy.id,
                    instrument_token=instrument.instrument_token,
                    tradingsymbol=instrument.tradingsymbol,
                    scan_data=json.dumps(scan_data),
                    signal_strength=signal_strength
                )
                db.session.add(scan_result)
                saved_count += 1

            db.session.commit()
            current_app.logger.info(f'Saved {saved_count} scan results for strategy {strategy_name}')
            return saved_count

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error saving scan results: {str(e)}')
            raise

    def get_scan_results(self, strategy_name=None, limit=50):
        """
        Get saved scan results

        Args:
            strategy_name: Optional strategy name filter
            limit: Maximum number of results

        Returns:
            list: Scan results
        """
        query = ScanResult.query.filter_by(user_id=self.user.id)

        if strategy_name:
            strategy = ScannerStrategy.query.filter_by(name=strategy_name).first()
            if strategy:
                query = query.filter_by(strategy_id=strategy.id)

        results = query.order_by(
            ScanResult.signal_strength.desc(),
            ScanResult.scan_timestamp.desc()
        ).limit(limit).all()

        return results
