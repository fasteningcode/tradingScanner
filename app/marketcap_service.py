"""
Market Cap Fetching Service

This service fetches market capitalization data from Yahoo Finance for all stocks
and stores it in the database. Uses yfinance library for reliable data access.
Implements rate limiting (1 request per second).
"""

import time
import json
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from flask import current_app
import yfinance as yf
from app import db
from app.models import Instrument, StockInformation, MarketCapFetchTask


# Global dictionary to track active fetch tasks
active_fetch_tasks = {}


class YahooFinanceMarketCapFetcher:
    """
    Fetches market cap data from Yahoo Finance using yfinance library
    """

    def __init__(self, rate_limit: float = 1.0):
        """
        Initialize fetcher with rate limiting

        Args:
            rate_limit: Minimum seconds between requests (default: 1.0)
        """
        self.rate_limit = rate_limit
        self.last_request_time = 0
        current_app.logger.info("Yahoo Finance fetcher initialized")

    def _rate_limit_wait(self):
        """Enforce rate limiting by waiting if necessary"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.rate_limit:
            wait_time = self.rate_limit - time_since_last_request
            time.sleep(wait_time)

        self.last_request_time = time.time()

    def fetch_stock_info(self, symbol: str) -> Optional[Dict]:
        """
        Fetch market cap information for a single stock from Yahoo Finance

        Args:
            symbol: Trading symbol (e.g., 'RELIANCE', 'TCS')

        Returns:
            Dictionary with market cap data or None if failed
        """
        # Enforce rate limiting
        self._rate_limit_wait()

        try:
            # Yahoo Finance uses .NS suffix for NSE stocks
            yahoo_symbol = f"{symbol}.NS"

            current_app.logger.info(f"Fetching market cap for {symbol} from Yahoo Finance ({yahoo_symbol})")

            # Fetch stock data using yfinance
            stock = yf.Ticker(yahoo_symbol)
            info = stock.info

            if not info or len(info) == 0:
                current_app.logger.warning(f"No data returned for {symbol}")
                return None

            # Extract company name
            company_name = info.get('longName') or info.get('shortName') or symbol

            # Extract market cap (Yahoo returns it in the stock's currency)
            # Convert to crores (1 crore = 10 million)
            market_cap = info.get('marketCap')
            total_market_cap = None
            if market_cap:
                # Convert from USD/INR to crores
                # Yahoo Finance returns market cap in the base currency
                total_market_cap = market_cap / 10000000  # Convert to crores

            # Free float market cap calculation
            # floatShares * current price
            float_shares = info.get('floatShares')
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            free_float_market_cap = None

            if float_shares and current_price:
                free_float_market_cap = (float_shares * current_price) / 10000000  # Convert to crores

            # Extract last traded price (LTP)
            last_traded_price = current_price

            # Extract outstanding shares (shares outstanding)
            outstanding_shares = info.get('sharesOutstanding')

            # Format market cap values for logging
            total_mc_str = f"{total_market_cap:.2f}" if total_market_cap else "None"
            ff_mc_str = f"{free_float_market_cap:.2f}" if free_float_market_cap else "None"
            ltp_str = f"{last_traded_price:.2f}" if last_traded_price else "None"
            os_str = f"{outstanding_shares:,}" if outstanding_shares else "None"
            fs_str = f"{float_shares:,}" if float_shares else "None"

            current_app.logger.info(
                f"Successfully fetched data for {symbol}: "
                f"Company={company_name}, TotalMC={total_mc_str} cr, FFMC={ff_mc_str} cr, "
                f"LTP={ltp_str}, OutstandingShares={os_str}, FloatShares={fs_str}"
            )

            return {
                'tradingsymbol': symbol,
                'company_name': company_name,
                'total_market_cap': total_market_cap,
                'free_float_market_cap': free_float_market_cap,
                'last_traded_price': last_traded_price,
                'outstanding_shares': outstanding_shares,
                'float_shares': float_shares,
                'last_updated': datetime.utcnow()
            }

        except Exception as e:
            current_app.logger.error(f"Error fetching data for {symbol}: {str(e)}")
            return None


def create_marketcap_fetch_task(user_id: int) -> MarketCapFetchTask:
    """
    Create a new market cap fetch task

    Args:
        user_id: ID of the user initiating the fetch

    Returns:
        Created MarketCapFetchTask instance
    """
    # Get all NIFTY 500 stocks
    instruments = Instrument.query.filter_by(
        exchange='NSE',
        instrument_type='EQ',
        is_nifty500=True
    ).all()

    total_stocks = len(instruments)

    # Create task
    task = MarketCapFetchTask(
        user_id=user_id,
        status='pending',
        total_stocks=total_stocks,
        completed_stocks=0,
        failed_stocks=0,
        total_api_calls=0,
        total_success=0,
        failed_stocks_list='[]'
    )

    db.session.add(task)
    db.session.commit()

    current_app.logger.info(
        f"Created market cap fetch task {task.id} for user {user_id} with {total_stocks} stocks"
    )

    return task


def run_marketcap_fetch_task(task_id: int, app):
    """
    Background worker function to fetch market cap data for all stocks

    Args:
        task_id: ID of the MarketCapFetchTask to process
        app: Flask application instance for context
    """
    fetcher = None  # Initialize fetcher variable for cleanup

    with app.app_context():
        try:
            # Get the task
            task = MarketCapFetchTask.query.get(task_id)
            if not task:
                current_app.logger.error(f"Task {task_id} not found")
                return

            # Mark task as running
            task.status = 'running'
            task.started_at = datetime.utcnow()
            db.session.commit()

            current_app.logger.info(f"Starting market cap fetch task {task_id}")

            # Get all NIFTY 500 stocks
            instruments = Instrument.query.filter_by(
                exchange='NSE',
                instrument_type='EQ',
                is_nifty500=True
            ).order_by(Instrument.tradingsymbol).all()

            # Initialize fetcher with 1 request per second rate limit
            current_app.logger.info("Initializing Yahoo Finance fetcher for market cap fetching...")
            fetcher = YahooFinanceMarketCapFetcher(rate_limit=1.0)
            current_app.logger.info("Fetcher initialized successfully")

            failed_stocks = []
            completed_count = 0
            success_count = 0

            # Process each stock
            for instrument in instruments:
                # Check if task was cancelled
                db.session.refresh(task)
                if task.status == 'cancelled':
                    current_app.logger.info(f"Task {task_id} was cancelled")
                    break

                symbol = instrument.tradingsymbol
                task.current_stock_symbol = symbol
                db.session.commit()

                current_app.logger.info(f"Task {task_id}: Fetching data for {symbol}")

                # Fetch market cap data
                stock_data = fetcher.fetch_stock_info(symbol)
                task.total_api_calls += 1

                if stock_data:
                    # Store or update in database
                    stock_info = StockInformation.query.filter_by(
                        tradingsymbol=symbol
                    ).first()

                    if stock_info:
                        # Update existing record
                        stock_info.company_name = stock_data.get('company_name')
                        stock_info.total_market_cap = stock_data.get('total_market_cap')
                        stock_info.free_float_market_cap = stock_data.get('free_float_market_cap')
                        stock_info.last_traded_price = stock_data.get('last_traded_price')
                        stock_info.outstanding_shares = stock_data.get('outstanding_shares')
                        stock_info.float_shares = stock_data.get('float_shares')
                        stock_info.last_updated = stock_data.get('last_updated')
                        stock_info.updated_at = datetime.utcnow()
                    else:
                        # Create new record
                        stock_info = StockInformation(
                            tradingsymbol=symbol,
                            company_name=stock_data.get('company_name'),
                            total_market_cap=stock_data.get('total_market_cap'),
                            free_float_market_cap=stock_data.get('free_float_market_cap'),
                            last_traded_price=stock_data.get('last_traded_price'),
                            outstanding_shares=stock_data.get('outstanding_shares'),
                            float_shares=stock_data.get('float_shares'),
                            last_updated=stock_data.get('last_updated')
                        )
                        db.session.add(stock_info)

                    success_count += 1
                    current_app.logger.info(f"Task {task_id}: SUCCESS for {symbol}")
                else:
                    # Failed to fetch
                    failed_stocks.append(symbol)
                    task.failed_stocks += 1
                    current_app.logger.warning(f"Task {task_id}: FAILED for {symbol}")

                completed_count += 1
                task.completed_stocks = completed_count
                task.total_success = success_count
                task.progress_percentage = (completed_count / task.total_stocks) * 100
                task.failed_stocks_list = json.dumps(failed_stocks)

                # Commit progress every stock
                db.session.commit()

            # Task completed
            task.status = 'completed'
            task.completed_at = datetime.utcnow()
            task.current_stock_symbol = None
            db.session.commit()

            current_app.logger.info(
                f"Market cap fetch task {task_id} completed: "
                f"{success_count} success, {len(failed_stocks)} failed"
            )

        except Exception as e:
            current_app.logger.error(f"Error in market cap fetch task {task_id}: {str(e)}")
            import traceback
            current_app.logger.error(f"Traceback: {traceback.format_exc()}")
            try:
                task = MarketCapFetchTask.query.get(task_id)
                if task:
                    task.status = 'failed'
                    task.error_message = str(e)
                    task.completed_at = datetime.utcnow()
                    db.session.commit()
            except:
                pass
        finally:
            # Remove from active tasks
            if task_id in active_fetch_tasks:
                del active_fetch_tasks[task_id]

            current_app.logger.info(f"Market cap fetch task {task_id} cleanup completed")


def start_marketcap_fetch(user_id: int, app) -> Tuple[bool, str, Optional[int]]:
    """
    Start a market cap fetch task in background thread

    Args:
        user_id: ID of the user initiating the fetch
        app: Flask application instance

    Returns:
        Tuple of (success, message, task_id)
    """
    # Check if there's already an active task for this user
    existing_task = MarketCapFetchTask.query.filter(
        MarketCapFetchTask.user_id == user_id,
        MarketCapFetchTask.status.in_(['pending', 'running'])
    ).first()

    if existing_task:
        return False, "A market cap fetch is already in progress", existing_task.id

    # Create new task
    task = create_marketcap_fetch_task(user_id)

    # Start background thread
    thread = threading.Thread(
        target=run_marketcap_fetch_task,
        args=(task.id, app),
        daemon=True
    )
    thread.start()

    # Track active task
    active_fetch_tasks[task.id] = {
        'thread': thread,
        'started_at': datetime.utcnow()
    }

    current_app.logger.info(f"Started market cap fetch task {task.id} in background")

    return True, "Market cap fetch started successfully", task.id


def get_marketcap_fetch_status(user_id: int) -> Optional[Dict]:
    """
    Get status of the current market cap fetch task for a user

    Args:
        user_id: ID of the user

    Returns:
        Dictionary with task status or None if no active task
    """
    task = MarketCapFetchTask.query.filter_by(user_id=user_id).order_by(
        MarketCapFetchTask.created_at.desc()
    ).first()

    if not task:
        return None

    return task.to_dict()


def cancel_marketcap_fetch(task_id: int) -> Tuple[bool, str]:
    """
    Cancel a running market cap fetch task

    Args:
        task_id: ID of the task to cancel

    Returns:
        Tuple of (success, message)
    """
    task = MarketCapFetchTask.query.get(task_id)

    if not task:
        return False, "Task not found"

    if task.status not in ['pending', 'running']:
        return False, f"Task is not running (status: {task.status})"

    # Mark as cancelled
    task.status = 'cancelled'
    task.completed_at = datetime.utcnow()
    db.session.commit()

    current_app.logger.info(f"Cancelled market cap fetch task {task_id}")

    return True, "Task cancelled successfully"


def get_marketcap_statistics() -> Dict:
    """
    Get statistics about stored market cap data

    Returns:
        Dictionary with statistics
    """
    total_stocks = StockInformation.query.count()

    stocks_with_total_mc = StockInformation.query.filter(
        StockInformation.total_market_cap.isnot(None)
    ).count()

    stocks_with_ff_mc = StockInformation.query.filter(
        StockInformation.free_float_market_cap.isnot(None)
    ).count()

    # Get most recent update
    latest_update = StockInformation.query.order_by(
        StockInformation.last_updated.desc()
    ).first()

    return {
        'total_stocks': total_stocks,
        'stocks_with_total_market_cap': stocks_with_total_mc,
        'stocks_with_free_float_market_cap': stocks_with_ff_mc,
        'latest_update': latest_update.last_updated.isoformat() if latest_update and latest_update.last_updated else None,
        'coverage_percentage': round((total_stocks / 503 * 100), 2) if total_stocks > 0 else 0
    }
