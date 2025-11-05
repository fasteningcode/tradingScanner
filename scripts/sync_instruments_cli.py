"""
Command-line script to sync instruments from Kite
Run this if you prefer CLI over the web UI button
"""

import sys
import os

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import create_app, db
from app.instruments_manager import InstrumentsManager

def main():
    print("=" * 70)
    print("  KITE INSTRUMENTS SYNC")
    print("=" * 70)
    print("\nThis script will download all instruments from Kite Connect.")
    print("Make sure you have valid Kite credentials configured.\n")

    response = input("Do you want to continue? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Sync cancelled.")
        return

    app = create_app()

    with app.app_context():
        try:
            print("\nDownloading instruments from Kite...")
            stats = InstrumentsManager.sync_instruments(exchange='NSE')

            print("\n" + "=" * 70)
            print("  SYNC COMPLETED!")
            print("=" * 70)
            print(f"\nStatistics:")
            print(f"  Created: {stats.get('created', 0)}")
            print(f"  Updated: {stats.get('updated', 0)}")
            print(f"  Skipped: {stats.get('skipped', 0)}")
            print(f"  Total: {stats.get('total', 0)}")

            # Check NIFTY 500 count
            from app.models import Instrument
            nifty500_count = Instrument.query.filter_by(
                exchange='NSE',
                instrument_type='EQ',
                is_nifty500=True
            ).count()

            print(f"\nNIFTY 500 stocks found: {nifty500_count}")

            if nifty500_count > 0:
                print("\n✓ Ready for sector migration!")
                print("Next step: Run 'python migrate_sectors.py'")
            else:
                print("\n⚠️  No NIFTY 500 stocks found.")
                print("You may need to:")
                print("  1. Make sure NIFTY 500 list is populated")
                print("  2. Check Kite connection")

        except Exception as e:
            print(f"\n❌ Error syncing instruments: {str(e)}")
            print("\nMake sure:")
            print("  1. You have a valid Kite connection")
            print("  2. Your Kite API key and access token are correct")
            print("  3. You're authenticated with Kite")
            return 1

    return 0

if __name__ == '__main__':
    exit(main())
