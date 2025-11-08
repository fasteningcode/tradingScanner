"""
Volume Dry-Up Scanner
Analyzes historical candlestick data to find stocks showing volume dry-up patterns
"""
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

def calculate_average_volume(candles: List[Dict], period: int = 20) -> float:
    """Calculate average volume over a period"""
    if len(candles) < period:
        return 0

    recent_candles = candles[-period:]
    total_volume = sum(c.get('volume', 0) for c in recent_candles)
    return total_volume / period

def is_volume_declining(candles: List[Dict], lookback: int = 5) -> bool:
    """Check if volume is declining over the lookback period"""
    if len(candles) < lookback:
        return False

    recent_candles = candles[-lookback:]
    volumes = [c.get('volume', 0) for c in recent_candles]

    # Check if each subsequent volume is lower (allowing for 1 exception)
    declining_count = 0
    for i in range(1, len(volumes)):
        if volumes[i] < volumes[i-1]:
            declining_count += 1

    # At least 3 out of 5 days should show declining volume
    return declining_count >= 3

def calculate_price_range(candles: List[Dict], lookback: int = 5) -> float:
    """Calculate price range as percentage over lookback period"""
    if len(candles) < lookback:
        return 100

    recent_candles = candles[-lookback:]
    highs = [c.get('high', 0) for c in recent_candles]
    lows = [c.get('low', 0) for c in recent_candles]

    max_high = max(highs)
    min_low = min(lows)

    if min_low == 0:
        return 100

    return ((max_high - min_low) / min_low) * 100

def is_price_above_ma(candles: List[Dict], ma_period: int = 50) -> bool:
    """Check if current price is above moving average"""
    if len(candles) < ma_period:
        return False

    ma_candles = candles[-ma_period:]
    avg_close = sum(c.get('close', 0) for c in ma_candles) / ma_period

    current_price = candles[-1].get('close', 0)
    return current_price > avg_close

def calculate_distance_from_high(candles: List[Dict], lookback: int = 52) -> float:
    """Calculate percentage distance from 52-week high"""
    if len(candles) < lookback:
        lookback = len(candles)

    if lookback == 0:
        return 100

    recent_candles = candles[-lookback:]
    highs = [c.get('high', 0) for c in recent_candles]
    max_high = max(highs)

    current_price = candles[-1].get('close', 0)

    if max_high == 0:
        return 100

    return ((max_high - current_price) / max_high) * 100

def scan_volume_dryup(db_path: str) -> List[Dict]:
    """
    Scan database for stocks showing volume dry-up patterns

    Criteria:
    1. Current volume < 50% of 20-day average volume
    2. Volume declining for 5+ consecutive sessions (at least 3 out of 5 days)
    3. Price in tight range (< 5% movement over last 5 days)
    4. Price above 50-day MA
    5. Price within 10% of 52-week high
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all stocks with daily historical data
    cursor.execute("""
        SELECT tradingsymbol, candlestick_data, last_downloaded
        FROM historical_data
        WHERE interval = 'day'
        AND candlestick_data IS NOT NULL
        AND candlestick_data != '[]'
    """)

    results = []
    total_stocks = 0

    for row in cursor.fetchall():
        total_stocks += 1
        tradingsymbol = row[0]
        candlestick_json = row[1]

        try:
            candles = json.loads(candlestick_json)

            # Need at least 60 days of data for proper analysis
            if len(candles) < 60:
                continue

            # Calculate metrics
            avg_volume_20 = calculate_average_volume(candles, 20)
            current_volume = candles[-1].get('volume', 0)

            # Criterion 1: Current volume < 50% of 20-day average
            if avg_volume_20 == 0 or current_volume > (avg_volume_20 * 0.5):
                continue

            # Criterion 2: Volume declining over last 5 days
            if not is_volume_declining(candles, 5):
                continue

            # Criterion 3: Price in tight range (< 5% over last 5 days)
            price_range = calculate_price_range(candles, 5)
            if price_range > 5.0:
                continue

            # Criterion 4: Price above 50-day MA
            if not is_price_above_ma(candles, 50):
                continue

            # Criterion 5: Price within 10% of 52-week high
            distance_from_high = calculate_distance_from_high(candles, 252)  # ~52 weeks
            if distance_from_high > 10.0:
                continue

            # Calculate additional metrics for reporting
            current_price = candles[-1].get('close', 0)
            volume_ratio = (current_volume / avg_volume_20) * 100 if avg_volume_20 > 0 else 0

            # Get last 5 days volumes for display
            last_5_volumes = [c.get('volume', 0) for c in candles[-5:]]

            results.append({
                'symbol': tradingsymbol,
                'current_price': round(current_price, 2),
                'current_volume': current_volume,
                'avg_volume_20d': int(avg_volume_20),
                'volume_ratio_pct': round(volume_ratio, 1),
                'price_range_5d_pct': round(price_range, 2),
                'distance_from_52w_high_pct': round(distance_from_high, 2),
                'last_5_volumes': last_5_volumes,
                'last_date': candles[-1].get('date', 'N/A')
            })

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Skip stocks with invalid data
            continue

    conn.close()

    # Sort by volume ratio (lowest first - most dry-up)
    results.sort(key=lambda x: x['volume_ratio_pct'])

    print(f"\n{'='*100}")
    print(f"VOLUME DRY-UP SCANNER RESULTS")
    print(f"{'='*100}")
    print(f"Total stocks analyzed: {total_stocks}")
    print(f"Stocks showing volume dry-up: {len(results)}")
    print(f"{'='*100}\n")

    if results:
        print(f"{'Symbol':<15} {'Price':<10} {'Curr Vol':<12} {'Avg Vol':<12} {'Vol %':<10} {'Range %':<10} {'From High %':<12} {'Last Date':<12}")
        print(f"{'-'*100}")

        for stock in results:
            print(f"{stock['symbol']:<15} "
                  f"{stock['current_price']:<10} "
                  f"{stock['current_volume']:<12} "
                  f"{stock['avg_volume_20d']:<12} "
                  f"{stock['volume_ratio_pct']:<10.1f} "
                  f"{stock['price_range_5d_pct']:<10.2f} "
                  f"{stock['distance_from_52w_high_pct']:<12.2f} "
                  f"{stock['last_date']:<12}")

        print(f"\n{'-'*100}")
        print(f"\nCRITERIA USED:")
        print(f"  1. Current volume < 50% of 20-day average")
        print(f"  2. Volume declining trend (at least 3 out of 5 days)")
        print(f"  3. Price in tight range (< 5% over last 5 days)")
        print(f"  4. Price above 50-day moving average")
        print(f"  5. Price within 10% of 52-week high")
        print(f"{'='*100}\n")

    return results

if __name__ == "__main__":
    db_path = "/Users/codenear/codenear-project-files/Aadhith/V1/instance/app.db"
    results = scan_volume_dryup(db_path)

    # Save results to JSON file
    if results:
        output_file = f"volume_dryup_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {output_file}")
