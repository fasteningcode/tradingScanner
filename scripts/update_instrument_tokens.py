#!/usr/bin/env python3
"""
Update Instrument Tokens from Kite API

This script fetches the latest instrument data from Kite API and updates
the instrument tokens in the database. This is critical because instrument
tokens can change over time, and outdated tokens will cause API calls to fail.

Usage:
    python update_instrument_tokens.py

Requirements:
    - Active Kite Connect session (user must be logged in)
    - Valid access token in the database
"""

import sys
import os
from datetime import datetime

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models import User, Instrument
from app.kite_auth import get_kite_client
from sqlalchemy import func


def update_instrument_tokens():
    """
    Update instrument tokens from Kite API

    Returns:
        Tuple of (success_count, updated_count, failed_count, error_message)
    """
    print("=" * 80)
    print("INSTRUMENT TOKEN UPDATE SCRIPT")
    print("=" * 80)
    print()

    # Get the first user with a valid Kite token
    print("Step 1: Finding user with valid Kite access token...")
    user = User.query.filter(
        User.kite_connected == True,
        User.kite_access_token.isnot(None)
    ).first()

    if not user:
        error_msg = "No user found with active Kite connection. Please login to Kite first."
        print(f"ERROR: {error_msg}")
        return (0, 0, 0, error_msg)

    print(f"✓ Found user: {user.username} (ID: {user.id})")
    print()

    # Check if token is valid
    print("Step 2: Validating Kite access token...")
    if not user.is_kite_token_valid():
        error_msg = "Kite access token has expired. Please reconnect to Kite."
        print(f"ERROR: {error_msg}")
        return (0, 0, 0, error_msg)

    print("✓ Access token is valid")
    print()

    # Initialize Kite client
    print("Step 3: Initializing Kite client...")
    try:
        kite = get_kite_client(access_token=user.kite_access_token)
        print("✓ Kite client initialized successfully")
        print()
    except Exception as e:
        error_msg = f"Failed to initialize Kite client: {str(e)}"
        print(f"ERROR: {error_msg}")
        return (0, 0, 0, error_msg)

    # Fetch instruments from Kite API
    print("Step 4: Fetching instruments from Kite API...")
    try:
        kite_instruments = kite.instruments()
        print(f"✓ Fetched {len(kite_instruments)} instruments from Kite API")
        print()
    except Exception as e:
        error_msg = f"Failed to fetch instruments from Kite: {str(e)}"
        print(f"ERROR: {error_msg}")
        return (0, 0, 0, error_msg)

    # Create a lookup dictionary for fast access
    # Key: (exchange, tradingsymbol)
    print("Step 5: Creating lookup dictionary...")
    kite_lookup = {}
    for inst in kite_instruments:
        key = (inst['exchange'], inst['tradingsymbol'])
        kite_lookup[key] = inst
    print(f"✓ Created lookup for {len(kite_lookup)} instruments")
    print()

    # Get all instruments from database
    print("Step 6: Loading instruments from database...")
    db_instruments = Instrument.query.all()
    print(f"✓ Loaded {len(db_instruments)} instruments from database")
    print()

    # Update tokens
    print("Step 7: Updating instrument tokens...")
    print("-" * 80)

    updated_count = 0
    no_change_count = 0
    not_found_count = 0
    error_count = 0

    for db_inst in db_instruments:
        key = (db_inst.exchange, db_inst.tradingsymbol)

        if key not in kite_lookup:
            print(f"⚠ NOT FOUND in Kite: {db_inst.tradingsymbol} ({db_inst.exchange})")
            not_found_count += 1
            continue

        kite_inst = kite_lookup[key]
        old_token = db_inst.instrument_token
        new_token = kite_inst['instrument_token']

        if old_token != new_token:
            print(f"→ UPDATING: {db_inst.tradingsymbol} ({db_inst.exchange})")
            print(f"  Old token: {old_token}")
            print(f"  New token: {new_token}")

            try:
                # Update the instrument token
                db_inst.instrument_token = new_token

                # Also update other fields that might have changed
                db_inst.name = kite_inst.get('name', db_inst.name)
                db_inst.exchange_token = kite_inst.get('exchange_token', db_inst.exchange_token)
                db_inst.lot_size = kite_inst.get('lot_size', db_inst.lot_size)
                db_inst.tick_size = kite_inst.get('tick_size', db_inst.tick_size)

                # Update last_updated timestamp
                db_inst.last_updated = datetime.utcnow()

                updated_count += 1
                print(f"  ✓ Updated successfully")
            except Exception as e:
                print(f"  ✗ Error updating: {str(e)}")
                error_count += 1
        else:
            # Token hasn't changed
            no_change_count += 1

    # Commit all changes
    print()
    print("-" * 80)
    print("Step 8: Committing changes to database...")
    try:
        db.session.commit()
        print("✓ All changes committed successfully")
    except Exception as e:
        db.session.rollback()
        error_msg = f"Failed to commit changes: {str(e)}"
        print(f"ERROR: {error_msg}")
        return (0, 0, 0, error_msg)

    # Print summary
    print()
    print("=" * 80)
    print("UPDATE SUMMARY")
    print("=" * 80)
    print(f"Total instruments in database:  {len(db_instruments)}")
    print(f"Instruments updated:            {updated_count}")
    print(f"Instruments unchanged:          {no_change_count}")
    print(f"Instruments not found in Kite:  {not_found_count}")
    print(f"Errors during update:           {error_count}")
    print("=" * 80)
    print()

    if updated_count > 0:
        print(f"✓ SUCCESS: Updated {updated_count} instrument token(s)")
    else:
        print("✓ All instrument tokens are already up to date")

    if not_found_count > 0:
        print(f"\n⚠ WARNING: {not_found_count} instruments not found in Kite API")
        print("  These instruments may have been delisted or symbols changed.")

    print()
    return (len(db_instruments), updated_count, not_found_count, None)


def check_nifty500_tokens():
    """
    Specifically check NIFTY 500 instrument tokens
    """
    print()
    print("=" * 80)
    print("NIFTY 500 TOKEN CHECK")
    print("=" * 80)
    print()

    nifty500 = Instrument.query.filter_by(is_nifty500=True).all()
    print(f"Found {len(nifty500)} NIFTY 500 instruments")
    print()

    # Show first 10 NIFTY 500 stocks with their tokens
    print("Sample of NIFTY 500 stocks (first 10):")
    print("-" * 80)
    print(f"{'Symbol':<15} {'Exchange':<10} {'Token':<15} {'Last Updated'}")
    print("-" * 80)

    for inst in nifty500[:10]:
        last_updated = inst.last_updated.strftime("%Y-%m-%d %H:%M") if inst.last_updated else "Never"
        print(f"{inst.tradingsymbol:<15} {inst.exchange:<10} {inst.instrument_token:<15} {last_updated}")

    print("-" * 80)
    print()


if __name__ == "__main__":
    # Create Flask app context
    app = create_app()

    with app.app_context():
        print()
        print("╔" + "=" * 78 + "╗")
        print("║" + " " * 20 + "INSTRUMENT TOKEN UPDATE UTILITY" + " " * 27 + "║")
        print("║" + " " * 78 + "║")
        print("║  This script updates instrument tokens from Kite API" + " " * 24 + "║")
        print("║  Critical for ensuring historical data downloads work properly" + " " * 12 + "║")
        print("╚" + "=" * 78 + "╝")
        print()

        # Ask for confirmation
        print("This will update instrument tokens in the database.")
        response = input("Do you want to continue? (yes/no): ").strip().lower()

        if response not in ['yes', 'y']:
            print("Aborted by user.")
            sys.exit(0)

        print()

        # Run the update
        total, updated, not_found, error = update_instrument_tokens()

        # Show NIFTY 500 specific info
        if error is None:
            check_nifty500_tokens()

        # Exit with appropriate code
        if error:
            sys.exit(1)
        elif updated > 0:
            print(f"✓ Update complete! {updated} tokens updated.")
            sys.exit(0)
        else:
            print("✓ All tokens are up to date. No changes needed.")
            sys.exit(0)
