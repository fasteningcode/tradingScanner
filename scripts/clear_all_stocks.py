#!/usr/bin/env python3
"""
Script to clear all stocks/instruments from the database
This will delete all instruments but keep the sector classification intact
"""

import sys
import os

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models import Instrument, WatchlistItem, MarketQuote


def clear_all_stocks():
    """Delete all instruments and related data from the database"""
    print("\n" + "="*80)
    print("CLEARING ALL STOCKS FROM DATABASE")
    print("="*80)

    # Count current data
    instrument_count = Instrument.query.count()
    watchlist_count = WatchlistItem.query.count()
    quote_count = MarketQuote.query.count()

    print(f"\nCurrent state:")
    print(f"  - Total Instruments/Stocks: {instrument_count}")
    print(f"  - Watchlist items: {watchlist_count}")
    print(f"  - Market quotes: {quote_count}")

    if instrument_count == 0:
        print("\nNo stocks found in database. Nothing to clear.")
        return 0

    # Show sample stocks before deletion
    print("\nSample stocks to be deleted:")
    sample_stocks = Instrument.query.limit(5).all()
    for stock in sample_stocks:
        print(f"  - {stock.tradingsymbol}: {stock.name}")

    if instrument_count > 5:
        print(f"  ... and {instrument_count - 5} more stocks")

    print("\n" + "="*80)
    print("WARNING: This will delete ALL stocks and related data!")
    print("="*80)

    # Delete related data first (watchlist items, quotes)
    if watchlist_count > 0:
        print(f"\n  → Deleting {watchlist_count} watchlist items...")
        WatchlistItem.query.delete()
        db.session.commit()
        print("  ✓ Watchlist items deleted")

    if quote_count > 0:
        print(f"\n  → Deleting {quote_count} market quotes...")
        MarketQuote.query.delete()
        db.session.commit()
        print("  ✓ Market quotes deleted")

    # Delete all instruments
    print(f"\n  → Deleting {instrument_count} stocks/instruments...")
    Instrument.query.delete()
    db.session.commit()
    print("  ✓ All stocks deleted")

    # Verify cleanup
    remaining_instruments = Instrument.query.count()
    remaining_watchlist = WatchlistItem.query.count()
    remaining_quotes = MarketQuote.query.count()

    if remaining_instruments == 0 and remaining_watchlist == 0 and remaining_quotes == 0:
        print("\n✓ Cleanup completed successfully!")
        print("\nFinal state:")
        print("  - Instruments: 0")
        print("  - Watchlist items: 0")
        print("  - Market quotes: 0")
        return 0
    else:
        raise Exception(
            f"Cleanup failed: {remaining_instruments} instruments, "
            f"{remaining_watchlist} watchlist items, "
            f"{remaining_quotes} quotes still remain"
        )


def main():
    """Main function"""
    print("\n" + "="*80)
    print("STOCK DATABASE CLEANUP SCRIPT")
    print("="*80)
    print("\nThis script will delete:")
    print("  - All stocks/instruments from the database")
    print("  - All watchlist items")
    print("  - All market quotes")
    print("\nNote: Sector classification will remain intact.")
    print("="*80)

    try:
        # Create Flask app context
        app = create_app()
        with app.app_context():
            # Clear all stocks
            result = clear_all_stocks()

            if result == 0:
                print("\n" + "="*80)
                print("CLEANUP COMPLETED SUCCESSFULLY")
                print("="*80)
                print("\nThe database is now clean and ready for fresh stock data.")
                print("You can now:")
                print("  - Import NIFTY 500 stocks using sync_instruments_cli.py")
                print("  - Add stocks manually from the stocks page")
                print("="*80 + "\n")

            return result

    except Exception as e:
        print(f"\n❌ ERROR: Cleanup failed!")
        print(f"Error details: {str(e)}")
        print("\nRolling back changes...")
        try:
            db.session.rollback()
            print("✓ Rollback completed")
        except:
            pass
        return 1


if __name__ == '__main__':
    sys.exit(main())
