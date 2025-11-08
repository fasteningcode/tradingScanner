"""
Detailed Volume Dry-Up Analysis
Shows last 10 days of price and volume data for stocks showing dry-up
"""
import json
import sqlite3
from datetime import datetime

def show_detailed_analysis(db_path: str, symbols: list):
    """Show detailed 10-day analysis for specified symbols"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for symbol in symbols:
        cursor.execute("""
            SELECT candlestick_data
            FROM historical_data
            WHERE tradingsymbol = ? AND interval = 'day'
        """, (symbol,))

        row = cursor.fetchone()
        if not row:
            continue

        candles = json.loads(row[0])
        if len(candles) < 10:
            continue

        # Get last 10 days
        last_10 = candles[-10:]

        # Calculate 20-day average volume
        avg_volume_20 = sum(c.get('volume', 0) for c in candles[-20:]) / 20

        print(f"\n{'='*120}")
        print(f"DETAILED ANALYSIS: {symbol}")
        print(f"{'='*120}")
        print(f"20-Day Average Volume: {int(avg_volume_20):,}")
        print(f"Current Price: {last_10[-1].get('close', 0)}")
        print(f"\nLast 10 Trading Days:")
        print(f"{'-'*120}")
        print(f"{'Date':<12} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10} {'Volume':<15} {'Vol vs Avg':<12} {'Price Change %':<15}")
        print(f"{'-'*120}")

        prev_close = last_10[0].get('close', 0)
        for candle in last_10:
            date = candle.get('date', 'N/A')
            open_price = candle.get('open', 0)
            high = candle.get('high', 0)
            low = candle.get('low', 0)
            close = candle.get('close', 0)
            volume = candle.get('volume', 0)

            vol_vs_avg = (volume / avg_volume_20 * 100) if avg_volume_20 > 0 else 0
            price_change = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0

            print(f"{date:<12} "
                  f"{open_price:<10.2f} "
                  f"{high:<10.2f} "
                  f"{low:<10.2f} "
                  f"{close:<10.2f} "
                  f"{volume:<15,} "
                  f"{vol_vs_avg:<12.1f}% "
                  f"{price_change:<+15.2f}%")

            prev_close = close

        print(f"{'-'*120}")

        # Volume trend analysis
        volumes = [c.get('volume', 0) for c in last_10]
        declining_days = sum(1 for i in range(1, len(volumes)) if volumes[i] < volumes[i-1])

        print(f"\nVOLUME TREND ANALYSIS:")
        print(f"  - Days with declining volume (out of 9): {declining_days}")
        print(f"  - Current volume is {(volumes[-1]/avg_volume_20*100):.1f}% of 20-day average")
        print(f"  - Volume decreased by {((1 - volumes[-1]/volumes[0])*100):.1f}% from 10 days ago")

        # Price consolidation analysis
        highs = [c.get('high', 0) for c in last_10]
        lows = [c.get('low', 0) for c in last_10]
        max_high = max(highs)
        min_low = min(lows)
        price_range = ((max_high - min_low) / min_low * 100) if min_low > 0 else 0

        print(f"\nPRICE CONSOLIDATION ANALYSIS:")
        print(f"  - 10-day high: {max_high:.2f}")
        print(f"  - 10-day low: {min_low:.2f}")
        print(f"  - Price range: {price_range:.2f}%")
        print(f"  - Status: {'TIGHT CONSOLIDATION' if price_range < 5 else 'MODERATE CONSOLIDATION'}")

        # Stage analysis
        ma_50 = sum(c.get('close', 0) for c in candles[-50:]) / 50 if len(candles) >= 50 else 0
        ma_150 = sum(c.get('close', 0) for c in candles[-150:]) / 150 if len(candles) >= 150 else 0
        current_price = last_10[-1].get('close', 0)

        print(f"\nMOVING AVERAGES:")
        print(f"  - 50-day MA: {ma_50:.2f} ({'Above' if current_price > ma_50 else 'Below'})")
        print(f"  - 150-day MA: {ma_150:.2f} ({'Above' if current_price > ma_150 else 'Below'})")

        print(f"\nINTERPRETATION:")
        if declining_days >= 5 and price_range < 5:
            print(f"  ✓ Strong volume dry-up signal with tight price consolidation")
            print(f"  ✓ Potential accumulation phase - watch for volume breakout")
        elif declining_days >= 3:
            print(f"  ✓ Moderate volume dry-up - monitor for continuation")
        else:
            print(f"  ⚠ Volume pattern not strongly declining")

        print(f"{'='*120}\n")

    conn.close()

if __name__ == "__main__":
    db_path = "/Users/codenear/codenear-project-files/Aadhith/V1/instance/app.db"

    # Load the results from the scanner
    import glob
    result_files = sorted(glob.glob("volume_dryup_results_*.json"), reverse=True)

    if result_files:
        with open(result_files[0], 'r') as f:
            results = json.load(f)

        symbols = [r['symbol'] for r in results]
        show_detailed_analysis(db_path, symbols)
    else:
        print("No volume dry-up results found. Please run volume_dryup_scanner.py first.")
