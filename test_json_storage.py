#!/usr/bin/env python3
"""
Test script to verify JSON storage functionality for historical data
"""
import sys
import json
from datetime import datetime
from app import create_app, db
from app.models import HistoricalData, Instrument

def test_json_storage():
    """Test that we can store and retrieve JSON data correctly"""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("Testing JSON Storage for Historical Data")
        print("=" * 60)

        # Test 1: Check existing data
        print("\n1. Checking existing historical data...")
        existing_data = HistoricalData.query.all()
        print(f"   Found {len(existing_data)} records in database")

        for data in existing_data:
            candles = data.get_candles()
            print(f"   - {data.tradingsymbol} ({data.interval}): {len(candles)} candles")
            if candles:
                print(f"     First candle: {candles[0]}")
                print(f"     Last candle: {candles[-1]}")

        # Test 2: Verify JSON structure
        print("\n2. Verifying JSON structure...")
        if existing_data:
            sample = existing_data[0]
            candles = sample.get_candles()

            if candles and len(candles) > 0:
                required_fields = ['date', 'open', 'high', 'low', 'close', 'volume', 'oi']
                first_candle = candles[0]

                print(f"   Checking candle structure: {first_candle}")
                missing_fields = [f for f in required_fields if f not in first_candle]

                if missing_fields:
                    print(f"   ❌ FAILED: Missing fields: {missing_fields}")
                    return False
                else:
                    print(f"   ✅ PASSED: All required fields present")
            else:
                print(f"   ⚠️  WARNING: No candles found in sample data")
        else:
            print(f"   ⚠️  WARNING: No historical data to verify")

        # Test 3: Test creating new data
        print("\n3. Testing JSON storage with mock data...")

        # Create test candles
        test_candles = [
            {
                'date': '2025-01-01',
                'open': 100.0,
                'high': 105.0,
                'low': 99.0,
                'close': 103.0,
                'volume': 1000,
                'oi': 0
            },
            {
                'date': '2025-01-02',
                'open': 103.0,
                'high': 108.0,
                'low': 102.0,
                'close': 107.0,
                'volume': 1500,
                'oi': 0
            }
        ]

        # Check if test data already exists
        test_data = HistoricalData.query.filter_by(
            tradingsymbol='TEST-STOCK',
            interval='day'
        ).first()

        if test_data:
            print(f"   Test data already exists, updating...")
            test_data.set_candles(test_candles)
            test_data.last_downloaded = datetime.utcnow()
        else:
            print(f"   Creating new test data...")
            test_data = HistoricalData(
                tradingsymbol='TEST-STOCK',
                interval='day',
                candlestick_data=json.dumps(test_candles),
                last_downloaded=datetime.utcnow(),
                created_on=datetime.utcnow(),
                updated_on=datetime.utcnow()
            )
            db.session.add(test_data)

        db.session.commit()
        print(f"   ✅ Test data saved successfully")

        # Test 4: Verify retrieval
        print("\n4. Verifying data retrieval...")
        retrieved_data = HistoricalData.query.filter_by(
            tradingsymbol='TEST-STOCK',
            interval='day'
        ).first()

        if retrieved_data:
            retrieved_candles = retrieved_data.get_candles()
            print(f"   Retrieved {len(retrieved_candles)} candles")
            print(f"   Candle count: {retrieved_data.get_candle_count()}")

            date_range = retrieved_data.get_date_range()
            print(f"   Date range: {date_range[0]} to {date_range[1]}")

            if retrieved_candles == test_candles:
                print(f"   ✅ PASSED: Retrieved data matches stored data")
            else:
                print(f"   ❌ FAILED: Data mismatch!")
                print(f"   Expected: {test_candles}")
                print(f"   Got: {retrieved_candles}")
                return False
        else:
            print(f"   ❌ FAILED: Could not retrieve test data")
            return False

        # Test 5: Check schema structure
        print("\n5. Verifying database schema...")
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = inspector.get_columns('historical_data')

        column_names = [col['name'] for col in columns]
        expected_columns = ['id', 'tradingsymbol', 'last_downloaded', 'interval',
                          'candlestick_data', 'created_on', 'updated_on']

        print(f"   Columns in table: {column_names}")

        if set(expected_columns).issubset(set(column_names)):
            print(f"   ✅ PASSED: All expected columns present")
        else:
            missing = set(expected_columns) - set(column_names)
            print(f"   ❌ FAILED: Missing columns: {missing}")
            return False

        # Test 6: Storage efficiency check
        print("\n6. Storage efficiency analysis...")
        all_data = HistoricalData.query.all()

        total_candles = sum(data.get_candle_count() for data in all_data)
        total_json_size = sum(len(data.candlestick_data) for data in all_data)

        print(f"   Total records: {len(all_data)}")
        print(f"   Total candles: {total_candles}")
        print(f"   Total JSON size: {total_json_size:,} bytes ({total_json_size / 1024:.2f} KB)")

        if total_candles > 0:
            avg_bytes_per_candle = total_json_size / total_candles
            print(f"   Average bytes per candle: {avg_bytes_per_candle:.2f}")

            # Old schema used ~441 bytes per candle
            # JSON should use ~60-80 bytes per candle
            if avg_bytes_per_candle < 150:
                print(f"   ✅ PASSED: Storage efficiency improved (< 150 bytes/candle)")
            else:
                print(f"   ⚠️  WARNING: Storage could be more efficient ({avg_bytes_per_candle:.2f} bytes/candle)")

        # Clean up test data
        print("\n7. Cleaning up test data...")
        db.session.delete(test_data)
        db.session.commit()
        print(f"   ✅ Test data cleaned up")

        print("\n" + "=" * 60)
        print("All tests completed successfully! ✅")
        print("=" * 60)

        return True

if __name__ == '__main__':
    try:
        success = test_json_storage()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
