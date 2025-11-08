"""
Strict Volume Dry-Up Scanner - Institutional Grade
===================================================
Focus: ONLY two critical factors that matter for volume dry-up breakouts

CRITERIA (Must pass BOTH):
1. Volume < 50% of 20-day average (Extreme dry-up)
2. Price consolidation < 6% over last 5 days (Tight range)

That's it. No complex scoring. Either it qualifies or it doesn't.
"""
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

class StrictVolumeDryUpScanner:
    """
    No-nonsense scanner for volume dry-up patterns
    Two criteria only - must pass both
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.results = []

    def calculate_volume_ratio(self, candles: List[Dict]) -> Optional[float]:
        """Calculate current volume as % of 20-day average"""
        if len(candles) < 20:
            return None

        # Get last 20 days volume
        volumes_20d = [c.get('volume', 0) for c in candles[-20:]]
        avg_20d = sum(volumes_20d) / 20

        current_volume = candles[-1].get('volume', 0)

        if avg_20d == 0:
            return None

        return (current_volume / avg_20d) * 100

    def calculate_consolidation_range(self, candles: List[Dict]) -> Optional[float]:
        """Calculate price consolidation range over last 5 days"""
        if len(candles) < 5:
            return None

        # Get last 5 days
        last_5 = candles[-5:]

        highs = [c.get('high', 0) for c in last_5]
        lows = [c.get('low', 0) for c in last_5]

        max_high = max(highs)
        min_low = min(lows)

        if min_low == 0:
            return None

        return ((max_high - min_low) / min_low) * 100

    def get_additional_metrics(self, candles: List[Dict]) -> Dict:
        """Get additional useful metrics for display"""
        if len(candles) < 252:
            lookback = len(candles)
        else:
            lookback = 252

        # 52-week high/low
        highs = [c.get('high', 0) for c in candles[-lookback:]]
        lows = [c.get('low', 0) for c in candles[-lookback:]]
        high_52w = max(highs)
        low_52w = min(lows)

        current_price = candles[-1].get('close', 0)

        dist_from_high = ((high_52w - current_price) / high_52w * 100) if high_52w > 0 else 100
        dist_from_low = ((current_price - low_52w) / low_52w * 100) if low_52w > 0 else 0

        # Moving averages
        ma_50 = sum(c.get('close', 0) for c in candles[-50:]) / 50 if len(candles) >= 50 else 0
        ma_150 = sum(c.get('close', 0) for c in candles[-150:]) / 150 if len(candles) >= 150 else 0
        ma_200 = sum(c.get('close', 0) for c in candles[-200:]) / 200 if len(candles) >= 200 else 0

        # Volume metrics
        volumes_20d = [c.get('volume', 0) for c in candles[-20:]]
        volumes_50d = [c.get('volume', 0) for c in candles[-50:]] if len(candles) >= 50 else volumes_20d
        avg_vol_20d = sum(volumes_20d) / len(volumes_20d)
        avg_vol_50d = sum(volumes_50d) / len(volumes_50d)

        # Last 10 days volumes
        last_10_volumes = [c.get('volume', 0) for c in candles[-10:]]

        # Count declining volume days
        declining_days = 0
        for i in range(1, len(last_10_volumes)):
            if last_10_volumes[-i] < last_10_volumes[-(i+1)]:
                declining_days += 1

        # Last 10 days price action
        last_10_candles = candles[-10:]

        return {
            'current_price': round(current_price, 2),
            'high_52w': round(high_52w, 2),
            'low_52w': round(low_52w, 2),
            'dist_from_52w_high_pct': round(dist_from_high, 2),
            'dist_from_52w_low_pct': round(dist_from_low, 2),
            'ma_50': round(ma_50, 2),
            'ma_150': round(ma_150, 2),
            'ma_200': round(ma_200, 2),
            'price_above_ma50': current_price > ma_50,
            'price_above_ma150': current_price > ma_150,
            'price_above_ma200': current_price > ma_200,
            'current_volume': candles[-1].get('volume', 0),
            'avg_vol_20d': int(avg_vol_20d),
            'avg_vol_50d': int(avg_vol_50d),
            'declining_volume_days': declining_days,
            'last_10_volumes': last_10_volumes,
            'last_10_candles': last_10_candles,
            'last_date': candles[-1].get('date', 'N/A')
        }

    def analyze_stock(self, symbol: str, candles: List[Dict]) -> Optional[Dict]:
        """
        Analyze stock - must pass BOTH criteria
        """
        if len(candles) < 20:
            return None

        # CRITERION 1: Volume < 50% of 20-day average
        volume_ratio = self.calculate_volume_ratio(candles)
        if volume_ratio is None or volume_ratio >= 50.0:
            return None

        # CRITERION 2: Price consolidation < 6%
        consolidation_range = self.calculate_consolidation_range(candles)
        if consolidation_range is None or consolidation_range >= 6.0:
            return None

        # Stock qualifies! Get additional metrics
        metrics = self.get_additional_metrics(candles)

        return {
            'symbol': symbol,
            'volume_ratio_pct': round(volume_ratio, 1),
            'consolidation_5d_pct': round(consolidation_range, 2),
            **metrics
        }

    def scan_all_stocks(self) -> List[Dict]:
        """Scan all stocks in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT tradingsymbol, candlestick_data
            FROM historical_data
            WHERE interval = 'day'
            AND candlestick_data IS NOT NULL
            AND candlestick_data != '[]'
        """)

        total_analyzed = 0

        for row in cursor.fetchall():
            total_analyzed += 1
            symbol = row[0]

            try:
                candles = json.loads(row[1])
                result = self.analyze_stock(symbol, candles)

                if result:
                    self.results.append(result)

            except (json.JSONDecodeError, Exception):
                continue

        conn.close()

        # Sort by volume ratio (lowest first = most extreme dry-up)
        self.results.sort(key=lambda x: x['volume_ratio_pct'])

        return self.results, total_analyzed

    def print_results(self, total_analyzed: int):
        """Print clean, institutional-style results"""
        print(f"\n{'='*140}")
        print(f"STRICT VOLUME DRY-UP SCANNER - INSTITUTIONAL GRADE")
        print(f"{'='*140}")
        print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Stocks Analyzed: {total_analyzed}")
        print(f"Qualifying Stocks: {len(self.results)}")
        print(f"\nCRITERIA (Must Pass BOTH):")
        print(f"  1. Current Volume < 50% of 20-day average")
        print(f"  2. Price Consolidation < 6% (5-day range)")
        print(f"{'='*140}\n")

        if not self.results:
            print("No stocks meet both criteria.\n")
            return

        # Summary table
        print(f"QUALIFYING STOCKS:\n")
        print(f"{'#':<4} {'Symbol':<15} {'Price':<10} {'Vol%':<10} {'Consol%':<10} {'From 52W High%':<15} {'MA50':<8} {'MA150':<8} {'MA200':<8}")
        print(f"{'-'*140}")

        for idx, stock in enumerate(self.results, 1):
            ma50_status = '✓' if stock['price_above_ma50'] else '✗'
            ma150_status = '✓' if stock['price_above_ma150'] else '✗'
            ma200_status = '✓' if stock['price_above_ma200'] else '✗'

            print(f"{idx:<4} "
                  f"{stock['symbol']:<15} "
                  f"{stock['current_price']:<10.2f} "
                  f"{stock['volume_ratio_pct']:<10.1f} "
                  f"{stock['consolidation_5d_pct']:<10.2f} "
                  f"{stock['dist_from_52w_high_pct']:<15.2f} "
                  f"{ma50_status:<8} "
                  f"{ma150_status:<8} "
                  f"{ma200_status:<8}")

        print(f"\n{'='*140}\n")

        # Detailed analysis for each stock
        print("DETAILED ANALYSIS - ALL QUALIFYING STOCKS")
        print(f"{'='*140}\n")

        for idx, stock in enumerate(self.results, 1):
            self.print_detailed_stock(idx, stock)

    def print_detailed_stock(self, rank: int, stock: Dict):
        """Print detailed analysis for a single stock"""
        print(f"{'#'}{rank}. {stock['symbol']}")
        print(f"{'-'*140}")

        # Classification based on metrics
        if stock['volume_ratio_pct'] < 30 and stock['consolidation_5d_pct'] < 3:
            classification = "⭐⭐⭐ EXTREME DRY-UP - HIGHEST PRIORITY"
        elif stock['volume_ratio_pct'] < 35 and stock['consolidation_5d_pct'] < 4:
            classification = "⭐⭐ STRONG DRY-UP - HIGH PRIORITY"
        elif stock['volume_ratio_pct'] < 40:
            classification = "⭐ GOOD DRY-UP - MONITOR"
        else:
            classification = "MODERATE DRY-UP - WATCH LIST"

        print(f"\nCLASSIFICATION: {classification}")

        print(f"\n✓ CRITERION 1: VOLUME DRY-UP")
        print(f"  Current Volume: {stock['current_volume']:,}")
        print(f"  20-Day Avg Volume: {stock['avg_vol_20d']:,}")
        print(f"  Current vs Avg: {stock['volume_ratio_pct']:.1f}% {'(EXTREME)' if stock['volume_ratio_pct'] < 30 else '(STRONG)' if stock['volume_ratio_pct'] < 40 else '(GOOD)'}")
        print(f"  Declining Days (last 10): {stock['declining_volume_days']}/9")

        print(f"\n✓ CRITERION 2: PRICE CONSOLIDATION")
        print(f"  5-Day Price Range: {stock['consolidation_5d_pct']:.2f}% {'(VERY TIGHT)' if stock['consolidation_5d_pct'] < 3 else '(TIGHT)' if stock['consolidation_5d_pct'] < 4.5 else '(GOOD)'}")
        print(f"  Current Price: ₹{stock['current_price']}")
        print(f"  52-Week High: ₹{stock['high_52w']} (Currently {stock['dist_from_52w_high_pct']:.2f}% below)")
        print(f"  52-Week Low: ₹{stock['low_52w']} (Currently {stock['dist_from_52w_low_pct']:.2f}% above)")

        print(f"\nMOVING AVERAGE POSITION:")
        print(f"  50-Day MA: ₹{stock['ma_50']} {'✓ Above' if stock['price_above_ma50'] else '✗ Below'}")
        print(f"  150-Day MA: ₹{stock['ma_150']} {'✓ Above' if stock['price_above_ma150'] else '✗ Below'}")
        print(f"  200-Day MA: ₹{stock['ma_200']} {'✓ Above' if stock['price_above_ma200'] else '✗ Below'}")

        # Stage determination
        if (stock['price_above_ma50'] and stock['price_above_ma150'] and
            stock['ma_50'] > stock['ma_150'] and stock['ma_150'] > stock['ma_200']):
            stage = "Stage 2 - ADVANCING (Ideal for breakout)"
        elif not stock['price_above_ma50'] and not stock['price_above_ma150']:
            stage = "Stage 4 - DECLINING (Avoid)"
        elif stock['price_above_ma50'] and stock['price_above_ma150'] and stock['ma_50'] < stock['ma_150']:
            stage = "Stage 3 - TOPPING (Caution)"
        else:
            stage = "Stage 1 - BASING (Emerging)"

        print(f"  Stage: {stage}")

        print(f"\nLAST 10 DAYS VOLUME TREND:")
        volumes = stock['last_10_volumes']
        for i in range(len(volumes)):
            vol = volumes[i]
            pct_of_avg = (vol / stock['avg_vol_20d'] * 100) if stock['avg_vol_20d'] > 0 else 0
            print(f"  Day {i-9}: {vol:,} ({pct_of_avg:.1f}% of avg)")

        print(f"\nLAST 10 DAYS PRICE ACTION:")
        print(f"  {'Date':<12} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10} {'Volume':<15}")
        for candle in stock['last_10_candles']:
            print(f"  {candle.get('date', 'N/A'):<12} "
                  f"{candle.get('open', 0):<10.2f} "
                  f"{candle.get('high', 0):<10.2f} "
                  f"{candle.get('low', 0):<10.2f} "
                  f"{candle.get('close', 0):<10.2f} "
                  f"{candle.get('volume', 0):<15,}")

        print(f"\nLast Updated: {stock['last_date']}")
        print(f"\n{'='*140}\n")

    def save_to_json(self):
        """Save results to JSON file"""
        if not self.results:
            return None

        output_file = f"strict_volume_dryup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        return output_file


def main():
    """Main execution"""
    db_path = "/Users/codenear/codenear-project-files/Aadhith/V1/instance/app.db"

    print("\nInitializing Strict Volume Dry-Up Scanner...")
    print("Applying only TWO criteria - no complex scoring, just pass/fail.\n")

    scanner = StrictVolumeDryUpScanner(db_path)
    results, total_analyzed = scanner.scan_all_stocks()
    scanner.print_results(total_analyzed)

    # Save results
    if results:
        output_file = scanner.save_to_json()
        print(f"Results saved to: {output_file}")
        print(f"\nINVESTMENT APPROACH:")
        print(f"  - These stocks show GENUINE volume dry-up + tight consolidation")
        print(f"  - Volume dry-up = Smart money accumulation")
        print(f"  - Tight consolidation = Coiled spring ready to break")
        print(f"  - Expected holding period: 2-4 weeks for breakout")
        print(f"  - Risk management: Stop loss below recent consolidation low or 50-day MA")
        print(f"  - Position sizing: Based on individual risk tolerance\n")


if __name__ == "__main__":
    main()
