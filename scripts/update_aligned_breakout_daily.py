#!/usr/bin/env python3
"""
Daily Aligned Breakout Metrics Update Script

This script should be run daily (after market close) to:
1. Update stock metrics (MA, volume, 52w high, etc.)
2. Update sector/subsector metrics
3. Update RS trends
4. Log results

Usage:
    python scripts/update_aligned_breakout_daily.py [--stocks-only] [--rs-trends-only]

Cron example (run at 6:30 PM on weekdays):
    30 18 * * 1-5 cd /path/to/V1 && source venv/bin/activate && python scripts/update_aligned_breakout_daily.py

Author: Claude Code
"""

import sys
import os
from datetime import datetime
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.aligned_breakout_calculator import (
    update_aligned_breakout_metrics,
    AlignedBreakoutCalculator
)

def main():
    parser = argparse.ArgumentParser(description='Update Aligned Breakout metrics')
    parser.add_argument('--stocks-only', action='store_true', help='Update only stock metrics')
    parser.add_argument('--rs-trends-only', action='store_true', help='Update only RS trends')
    parser.add_argument('--limit', type=int, help='Limit number of stocks (for testing)')
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        print('=' * 80)
        print('ALIGNED BREAKOUT DAILY UPDATE')
        print('=' * 80)
        print(f'Started at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print()

        results = {}

        try:
            if args.rs_trends_only:
                # Update RS trends only
                print('Updating RS trends...')
                calc = AlignedBreakoutCalculator()
                results['rs_trends'] = calc.update_all_rs_trends()

                print()
                print('RS Trend Update Results:')
                print(f'  Stocks: {results["rs_trends"]["stocks"]["success"]}/{results["rs_trends"]["stocks"]["total"]} success')
                print(f'  Sectors: {results["rs_trends"]["sectors"]["success"]}/{results["rs_trends"]["sectors"]["total"]} success')
                print(f'  SubSectors: {results["rs_trends"]["subsectors"]["success"]}/{results["rs_trends"]["subsectors"]["total"]} success')

            elif args.stocks_only:
                # Update stock metrics only
                print('Updating stock metrics...')
                results['stocks'] = update_aligned_breakout_metrics(limit=args.limit)

                print()
                print('Stock Metrics Update Results:')
                print(f'  Total: {results["stocks"]["total"]}')
                print(f'  Success: {results["stocks"]["success"]}')
                print(f'  Failed: {results["stocks"]["failed"]}')
                if results["stocks"]["failed"] > 0:
                    print(f'  Failed symbols: {results["stocks"]["failed_symbols"][:10]}...')

            else:
                # Full update (default)
                print('Step 1/3: Updating stock metrics...')
                results['stocks'] = update_aligned_breakout_metrics(limit=args.limit)

                print()
                print('Stock Metrics Update Results:')
                print(f'  Total: {results["stocks"]["total"]}')
                print(f'  Success: {results["stocks"]["success"]}')
                print(f'  Failed: {results["stocks"]["failed"]}')

                print()
                print('Step 2/3: Updating sector/subsector metrics...')
                calc = AlignedBreakoutCalculator()
                results['sectors'] = calc.update_all_sector_subsector_metrics()

                print()
                print('Sector/SubSector Metrics Update Results:')
                print(f'  Sectors: {results["sectors"]["sectors"]["success"]}/{results["sectors"]["sectors"]["total"]} success')
                print(f'  SubSectors: {results["sectors"]["subsectors"]["success"]}/{results["sectors"]["subsectors"]["total"]} success')

                print()
                print('Step 3/3: Updating RS trends...')
                results['rs_trends'] = calc.update_all_rs_trends()

                print()
                print('RS Trend Update Results:')
                print(f'  Stocks: {results["rs_trends"]["stocks"]["success"]}/{results["rs_trends"]["stocks"]["total"]} snapshots')
                print(f'  Sectors: {results["rs_trends"]["sectors"]["success"]}/{results["rs_trends"]["sectors"]["total"]} snapshots')
                print(f'  SubSectors: {results["rs_trends"]["subsectors"]["success"]}/{results["rs_trends"]["subsectors"]["total"]} snapshots')

            print()
            print('=' * 80)
            print(f'Completed at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
            print('Status: SUCCESS')
            print('=' * 80)

            return 0

        except Exception as e:
            print()
            print('=' * 80)
            print(f'ERROR: {str(e)}')
            print('=' * 80)
            import traceback
            traceback.print_exc()
            return 1


if __name__ == '__main__':
    sys.exit(main())
