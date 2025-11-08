"""
Institutional-Grade Volume Dry-Up Analyzer
========================================
Designed for institutional investors seeking accumulation patterns that precede major breakouts.
Focus: Monthly holding period with high-probability setups.

Key Principle: Volume dry-up after a trend = Smart money accumulation = Precursor to breakout
"""
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import statistics

class InstitutionalVolumeDryUpAnalyzer:
    """
    Institutional-grade analyzer for volume dry-up patterns
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.results = []

    def calculate_volume_metrics(self, candles: List[Dict]) -> Dict:
        """Calculate comprehensive volume metrics"""
        if len(candles) < 100:
            return None

        # Multiple timeframe volume averages
        vol_5d = [c.get('volume', 0) for c in candles[-5:]]
        vol_10d = [c.get('volume', 0) for c in candles[-10:]]
        vol_20d = [c.get('volume', 0) for c in candles[-20:]]
        vol_50d = [c.get('volume', 0) for c in candles[-50:]]
        vol_100d = [c.get('volume', 0) for c in candles[-100:]]

        avg_5d = sum(vol_5d) / len(vol_5d)
        avg_10d = sum(vol_10d) / len(vol_10d)
        avg_20d = sum(vol_20d) / len(vol_20d)
        avg_50d = sum(vol_50d) / len(vol_50d)
        avg_100d = sum(vol_100d) / len(vol_100d)

        current_volume = candles[-1].get('volume', 0)

        # Volume trend analysis
        volume_declining_days = 0
        for i in range(1, min(10, len(vol_10d))):
            if vol_10d[-i] < vol_10d[-(i+1)]:
                volume_declining_days += 1

        # Calculate volume standard deviation for 50-day period
        vol_std_50d = statistics.stdev(vol_50d) if len(vol_50d) > 1 else 0

        return {
            'current_volume': current_volume,
            'avg_5d': avg_5d,
            'avg_10d': avg_10d,
            'avg_20d': avg_20d,
            'avg_50d': avg_50d,
            'avg_100d': avg_100d,
            'volume_declining_days': volume_declining_days,
            'vol_std_50d': vol_std_50d,
            'ratio_vs_20d': (current_volume / avg_20d * 100) if avg_20d > 0 else 0,
            'ratio_vs_50d': (current_volume / avg_50d * 100) if avg_50d > 0 else 0,
            'avg_5d_vs_50d': (avg_5d / avg_50d * 100) if avg_50d > 0 else 0,
            'vol_5d_array': vol_5d,
            'vol_10d_array': vol_10d
        }

    def calculate_price_metrics(self, candles: List[Dict]) -> Dict:
        """Calculate comprehensive price metrics"""
        if len(candles) < 200:
            return None

        current_price = candles[-1].get('close', 0)

        # Moving averages
        closes_10d = [c.get('close', 0) for c in candles[-10:]]
        closes_20d = [c.get('close', 0) for c in candles[-20:]]
        closes_50d = [c.get('close', 0) for c in candles[-50:]]
        closes_150d = [c.get('close', 0) for c in candles[-150:]]
        closes_200d = [c.get('close', 0) for c in candles[-200:]]

        ma_10 = sum(closes_10d) / len(closes_10d)
        ma_20 = sum(closes_20d) / len(closes_20d)
        ma_50 = sum(closes_50d) / len(closes_50d)
        ma_150 = sum(closes_150d) / len(closes_150d)
        ma_200 = sum(closes_200d) / len(closes_200d)

        # 52-week high/low
        highs_252d = [c.get('high', 0) for c in candles[-252:]] if len(candles) >= 252 else [c.get('high', 0) for c in candles]
        lows_252d = [c.get('low', 0) for c in candles[-252:]] if len(candles) >= 252 else [c.get('low', 0) for c in candles]
        high_52w = max(highs_252d)
        low_52w = min(lows_252d)

        # Recent consolidation range (last 10 days)
        highs_10d = [c.get('high', 0) for c in candles[-10:]]
        lows_10d = [c.get('low', 0) for c in candles[-10:]]
        high_10d = max(highs_10d)
        low_10d = min(lows_10d)

        # Consolidation range (last 5 days for tighter analysis)
        highs_5d = [c.get('high', 0) for c in candles[-5:]]
        lows_5d = [c.get('low', 0) for c in candles[-5:]]
        high_5d = max(highs_5d)
        low_5d = min(lows_5d)

        # Price volatility
        price_std_20d = statistics.stdev(closes_20d) if len(closes_20d) > 1 else 0

        # Calculate distances
        dist_from_52w_high = ((high_52w - current_price) / high_52w * 100) if high_52w > 0 else 100
        dist_from_52w_low = ((current_price - low_52w) / low_52w * 100) if low_52w > 0 else 0

        consolidation_range_10d = ((high_10d - low_10d) / low_10d * 100) if low_10d > 0 else 100
        consolidation_range_5d = ((high_5d - low_5d) / low_5d * 100) if low_5d > 0 else 100

        return {
            'current_price': current_price,
            'ma_10': ma_10,
            'ma_20': ma_20,
            'ma_50': ma_50,
            'ma_150': ma_150,
            'ma_200': ma_200,
            'high_52w': high_52w,
            'low_52w': low_52w,
            'dist_from_52w_high': dist_from_52w_high,
            'dist_from_52w_low': dist_from_52w_low,
            'consolidation_range_10d': consolidation_range_10d,
            'consolidation_range_5d': consolidation_range_5d,
            'price_std_20d': price_std_20d,
            'price_above_ma50': current_price > ma_50,
            'price_above_ma150': current_price > ma_150,
            'price_above_ma200': current_price > ma_200,
            'ma50_above_ma150': ma_50 > ma_150,
            'ma150_above_ma200': ma_150 > ma_200
        }

    def calculate_stage(self, price_metrics: Dict) -> int:
        """
        Determine Weinstein stage
        Stage 1: Basing (not ideal for breakout)
        Stage 2: Advancing (IDEAL - with dry-up = accumulation before continuation)
        Stage 3: Topping (risky)
        Stage 4: Declining (avoid)
        """
        pm = price_metrics

        # Stage 2 characteristics (IDEAL)
        if (pm['price_above_ma50'] and
            pm['price_above_ma150'] and
            pm['ma50_above_ma150'] and
            pm['ma150_above_ma200']):
            return 2

        # Stage 3 characteristics (Topping)
        if (pm['price_above_ma50'] and
            pm['price_above_ma150'] and
            not pm['ma50_above_ma150']):
            return 3

        # Stage 4 characteristics (Declining)
        if (not pm['price_above_ma50'] and
            not pm['price_above_ma150']):
            return 4

        # Stage 1 (Basing)
        return 1

    def calculate_institutional_score(self, vol_metrics: Dict, price_metrics: Dict, stage: int) -> Tuple[float, Dict]:
        """
        Calculate institutional accumulation score (0-100)
        Higher score = Higher probability of breakout
        """
        score = 0
        details = {}

        # 1. VOLUME DRY-UP QUALITY (40 points max)
        # Current volume vs 20-day average
        vol_ratio_20d = vol_metrics['ratio_vs_20d']
        if vol_ratio_20d <= 20:
            score += 15
            details['vol_vs_20d'] = '15/15 (Extreme dry-up <20%)'
        elif vol_ratio_20d <= 30:
            score += 12
            details['vol_vs_20d'] = '12/15 (Strong dry-up <30%)'
        elif vol_ratio_20d <= 40:
            score += 8
            details['vol_vs_20d'] = '8/15 (Good dry-up <40%)'
        elif vol_ratio_20d <= 50:
            score += 5
            details['vol_vs_20d'] = '5/15 (Moderate dry-up <50%)'
        else:
            details['vol_vs_20d'] = '0/15 (Insufficient dry-up)'

        # 5-day avg volume vs 50-day avg (sustained dry-up)
        avg_5d_vs_50d = vol_metrics['avg_5d_vs_50d']
        if avg_5d_vs_50d <= 40:
            score += 15
            details['sustained_dryup'] = '15/15 (Sustained 5d<40% of 50d)'
        elif avg_5d_vs_50d <= 50:
            score += 10
            details['sustained_dryup'] = '10/15 (Sustained 5d<50% of 50d)'
        elif avg_5d_vs_50d <= 60:
            score += 5
            details['sustained_dryup'] = '5/15 (Moderate sustained dry-up)'
        else:
            details['sustained_dryup'] = '0/15 (No sustained dry-up)'

        # Volume declining trend consistency
        declining_days = vol_metrics['volume_declining_days']
        if declining_days >= 7:
            score += 10
            details['vol_trend'] = '10/10 (7+ declining days)'
        elif declining_days >= 5:
            score += 7
            details['vol_trend'] = '7/10 (5-6 declining days)'
        elif declining_days >= 3:
            score += 4
            details['vol_trend'] = '4/10 (3-4 declining days)'
        else:
            details['vol_trend'] = '0/10 (Inconsistent decline)'

        # 2. PRICE CONSOLIDATION (25 points max)
        # Tight consolidation = coiling for breakout
        consol_5d = price_metrics['consolidation_range_5d']
        if consol_5d <= 2.0:
            score += 15
            details['consolidation'] = '15/15 (Very tight <2%)'
        elif consol_5d <= 3.0:
            score += 12
            details['consolidation'] = '12/15 (Tight <3%)'
        elif consol_5d <= 4.0:
            score += 8
            details['consolidation'] = '8/15 (Good <4%)'
        elif consol_5d <= 5.0:
            score += 5
            details['consolidation'] = '5/15 (Moderate <5%)'
        else:
            details['consolidation'] = '0/15 (Too wide for dry-up pattern)'

        # Distance from 52-week high (institutional accumulation near highs)
        dist_from_high = price_metrics['dist_from_52w_high']
        if dist_from_high <= 5:
            score += 10
            details['position'] = '10/10 (Near 52w high <5%)'
        elif dist_from_high <= 10:
            score += 7
            details['position'] = '7/10 (Close to 52w high <10%)'
        elif dist_from_high <= 15:
            score += 4
            details['position'] = '4/10 (Moderate distance <15%)'
        else:
            details['position'] = '0/10 (Too far from 52w high)'

        # 3. STAGE ANALYSIS (20 points max)
        if stage == 2:
            score += 20
            details['stage'] = '20/20 (Stage 2 - IDEAL for breakout)'
        elif stage == 1:
            score += 10
            details['stage'] = '10/20 (Stage 1 - Emerging from base)'
        elif stage == 3:
            score += 5
            details['stage'] = '5/20 (Stage 3 - Topping risk)'
        else:
            details['stage'] = '0/20 (Stage 4 - Downtrend, AVOID)'

        # 4. MOVING AVERAGE STRUCTURE (15 points max)
        ma_points = 0
        if price_metrics['price_above_ma50']:
            ma_points += 5
        if price_metrics['ma50_above_ma150']:
            ma_points += 5
        if price_metrics['ma150_above_ma200']:
            ma_points += 5

        score += ma_points
        details['ma_structure'] = f'{ma_points}/15 (MA alignment)'

        return min(score, 100), details

    def analyze_stock(self, symbol: str, candles: List[Dict]) -> Optional[Dict]:
        """Perform comprehensive institutional analysis on a stock"""

        # Need sufficient data
        if len(candles) < 200:
            return None

        # Calculate all metrics
        vol_metrics = self.calculate_volume_metrics(candles)
        price_metrics = self.calculate_price_metrics(candles)

        if not vol_metrics or not price_metrics:
            return None

        # Determine stage
        stage = self.calculate_stage(price_metrics)

        # Calculate institutional score
        inst_score, score_details = self.calculate_institutional_score(
            vol_metrics, price_metrics, stage
        )

        # INSTITUTIONAL FILTERS - These MUST pass
        # Filter 1: Volume must be dry (current < 50% of 20-day avg)
        if vol_metrics['ratio_vs_20d'] > 50:
            return None

        # Filter 2: Sustained dry-up (5-day avg < 65% of 50-day avg)
        if vol_metrics['avg_5d_vs_50d'] > 65:
            return None

        # Filter 3: Price consolidation (5-day range < 6%)
        if price_metrics['consolidation_range_5d'] > 6.0:
            return None

        # Filter 4: Must be in Stage 2 or emerging Stage 1 (no Stage 4)
        if stage == 4:
            return None

        # Filter 5: Price above 50-day MA (strength)
        if not price_metrics['price_above_ma50']:
            return None

        # Filter 6: Not too far from 52-week high (< 20%)
        if price_metrics['dist_from_52w_high'] > 20:
            return None

        # Calculate expected breakout probability
        if inst_score >= 80:
            breakout_probability = "VERY HIGH (80-90%)"
            recommendation = "STRONG BUY - Excellent accumulation pattern"
        elif inst_score >= 70:
            breakout_probability = "HIGH (70-80%)"
            recommendation = "BUY - Good accumulation pattern"
        elif inst_score >= 60:
            breakout_probability = "MODERATE-HIGH (60-70%)"
            recommendation = "ACCUMULATE - Watch for confirmation"
        elif inst_score >= 50:
            breakout_probability = "MODERATE (50-60%)"
            recommendation = "WATCH - Early stage pattern"
        else:
            breakout_probability = "LOW (<50%)"
            recommendation = "MONITOR - Weak pattern"

        # Determine expected breakout timeframe
        vol_ratio = vol_metrics['ratio_vs_20d']
        consol_range = price_metrics['consolidation_range_5d']

        if vol_ratio < 30 and consol_range < 3:
            expected_timeframe = "1-2 weeks (Coiled spring)"
        elif vol_ratio < 40 and consol_range < 4:
            expected_timeframe = "2-3 weeks (Building pressure)"
        else:
            expected_timeframe = "3-4 weeks (Early accumulation)"

        return {
            'symbol': symbol,
            'institutional_score': round(inst_score, 1),
            'breakout_probability': breakout_probability,
            'recommendation': recommendation,
            'expected_timeframe': expected_timeframe,
            'stage': stage,
            'current_price': round(price_metrics['current_price'], 2),
            'volume_metrics': {
                'current_volume': vol_metrics['current_volume'],
                'avg_20d': int(vol_metrics['avg_20d']),
                'avg_50d': int(vol_metrics['avg_50d']),
                'current_vs_20d_pct': round(vol_metrics['ratio_vs_20d'], 1),
                'current_vs_50d_pct': round(vol_metrics['ratio_vs_50d'], 1),
                'avg_5d_vs_50d_pct': round(vol_metrics['avg_5d_vs_50d'], 1),
                'declining_days': vol_metrics['volume_declining_days'],
                'last_5_volumes': vol_metrics['vol_5d_array']
            },
            'price_metrics': {
                'consolidation_5d_pct': round(price_metrics['consolidation_range_5d'], 2),
                'consolidation_10d_pct': round(price_metrics['consolidation_range_10d'], 2),
                'dist_from_52w_high_pct': round(price_metrics['dist_from_52w_high'], 2),
                'dist_from_52w_low_pct': round(price_metrics['dist_from_52w_low'], 2),
                'ma_50': round(price_metrics['ma_50'], 2),
                'ma_150': round(price_metrics['ma_150'], 2),
                'ma_200': round(price_metrics['ma_200'], 2),
                '52w_high': round(price_metrics['high_52w'], 2),
                '52w_low': round(price_metrics['low_52w'], 2)
            },
            'score_breakdown': score_details,
            'last_date': candles[-1].get('date', 'N/A')
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

            except (json.JSONDecodeError, Exception) as e:
                continue

        conn.close()

        # Sort by institutional score (highest first)
        self.results.sort(key=lambda x: x['institutional_score'], reverse=True)

        return self.results, total_analyzed

    def print_results(self, total_analyzed: int):
        """Print detailed institutional analysis report"""
        print(f"\n{'='*140}")
        print(f"INSTITUTIONAL VOLUME DRY-UP ANALYSIS - BREAKOUT CANDIDATES")
        print(f"{'='*140}")
        print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Stocks Analyzed: {total_analyzed}")
        print(f"Qualifying Candidates: {len(self.results)}")
        print(f"Holding Period: 1 Month (30 days)")
        print(f"{'='*140}\n")

        if not self.results:
            print("No stocks meet the institutional-grade criteria for volume dry-up accumulation.")
            return

        # Summary table
        print(f"{'Rank':<6} {'Symbol':<15} {'Score':<8} {'Stage':<8} {'Price':<10} {'Vol%':<8} {'Consol%':<10} {'From High%':<12} {'Probability':<25}")
        print(f"{'-'*140}")

        for idx, stock in enumerate(self.results, 1):
            print(f"{idx:<6} "
                  f"{stock['symbol']:<15} "
                  f"{stock['institutional_score']:<8.1f} "
                  f"Stage {stock['stage']:<6} "
                  f"{stock['current_price']:<10.2f} "
                  f"{stock['volume_metrics']['current_vs_20d_pct']:<8.1f} "
                  f"{stock['price_metrics']['consolidation_5d_pct']:<10.2f} "
                  f"{stock['price_metrics']['dist_from_52w_high_pct']:<12.2f} "
                  f"{stock['breakout_probability']:<25}")

        print(f"\n{'='*140}\n")

        # Detailed analysis for top candidates
        print("DETAILED ANALYSIS - TOP CANDIDATES")
        print(f"{'='*140}\n")

        for idx, stock in enumerate(self.results[:5], 1):  # Top 5
            self.print_detailed_stock(idx, stock)

    def print_detailed_stock(self, rank: int, stock: Dict):
        """Print detailed analysis for a single stock"""
        print(f"#{rank}. {stock['symbol']} - Institutional Score: {stock['institutional_score']}/100")
        print(f"{'-'*140}")

        print(f"\nRECOMMENDATION: {stock['recommendation']}")
        print(f"BREAKOUT PROBABILITY: {stock['breakout_probability']}")
        print(f"EXPECTED TIMEFRAME: {stock['expected_timeframe']}")
        print(f"STAGE: {stock['stage']} - {'ADVANCING (Ideal)' if stock['stage'] == 2 else 'BASING' if stock['stage'] == 1 else 'TOPPING (Caution)' if stock['stage'] == 3 else 'DECLINING'}")

        print(f"\nVOLUME ANALYSIS:")
        vm = stock['volume_metrics']
        print(f"  Current Volume: {vm['current_volume']:,}")
        print(f"  20-Day Avg: {vm['avg_20d']:,} | Current is {vm['current_vs_20d_pct']:.1f}% of average {'✓' if vm['current_vs_20d_pct'] < 40 else ''}")
        print(f"  50-Day Avg: {vm['avg_50d']:,} | Current is {vm['current_vs_50d_pct']:.1f}% of average")
        print(f"  5-Day Avg vs 50-Day Avg: {vm['avg_5d_vs_50d_pct']:.1f}% {'✓ SUSTAINED DRY-UP' if vm['avg_5d_vs_50d_pct'] < 50 else ''}")
        print(f"  Declining Days (last 10): {vm['declining_days']}/9 {'✓' if vm['declining_days'] >= 5 else ''}")
        print(f"  Last 5 Days Volume: {[f'{v:,}' for v in vm['last_5_volumes']]}")

        print(f"\nPRICE ANALYSIS:")
        pm = stock['price_metrics']
        print(f"  Current Price: ₹{stock['current_price']}")
        print(f"  52-Week High: ₹{pm['52w_high']} (Currently {pm['dist_from_52w_high_pct']:.2f}% below) {'✓ NEAR HIGH' if pm['dist_from_52w_high_pct'] < 10 else ''}")
        print(f"  52-Week Low: ₹{pm['52w_low']} (Currently {pm['dist_from_52w_low_pct']:.2f}% above)")
        print(f"  5-Day Consolidation Range: {pm['consolidation_5d_pct']:.2f}% {'✓ TIGHT' if pm['consolidation_5d_pct'] < 3 else ''}")
        print(f"  10-Day Consolidation Range: {pm['consolidation_10d_pct']:.2f}%")

        print(f"\nMOVING AVERAGES:")
        print(f"  50-Day MA: ₹{pm['ma_50']} {'✓ Above' if stock['current_price'] > pm['ma_50'] else '✗ Below'}")
        print(f"  150-Day MA: ₹{pm['ma_150']} {'✓ Above' if stock['current_price'] > pm['ma_150'] else '✗ Below'}")
        print(f"  200-Day MA: ₹{pm['ma_200']} {'✓ Above' if stock['current_price'] > pm['ma_200'] else '✗ Below'}")

        print(f"\nSCORE BREAKDOWN:")
        for criterion, score_text in stock['score_breakdown'].items():
            print(f"  {criterion}: {score_text}")

        print(f"\nLast Updated: {stock['last_date']}")
        print(f"\n{'='*140}\n")


def main():
    """Main execution"""
    db_path = "/Users/codenear/codenear-project-files/Aadhith/V1/instance/app.db"

    print("\nInitializing Institutional Volume Dry-Up Analyzer...")
    print("Scanning for accumulation patterns that precede major breakouts...\n")

    analyzer = InstitutionalVolumeDryUpAnalyzer(db_path)
    results, total_analyzed = analyzer.scan_all_stocks()
    analyzer.print_results(total_analyzed)

    # Save results to JSON
    if results:
        output_file = f"institutional_dryup_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {output_file}")
        print(f"\nREMINDER: This analysis identifies accumulation patterns. ")
        print(f"Always use proper position sizing and risk management.")
        print(f"Recommended: Scale in over 1-2 weeks, set stop loss at 50-day MA or recent support.\n")


if __name__ == "__main__":
    main()
