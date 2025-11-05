#!/usr/bin/env python3
"""
Test with exact same parameters as working Postman request
"""
import sys
import os
from datetime import datetime

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models import User
from kiteconnect import KiteConnect

def test_exact_postman():
    """Test with exact same parameters as Postman"""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("Testing with EXACT Postman Parameters")
        print("=" * 60)

        # Get user
        user = User.query.get(1)
        if not user or not user.kite_access_token:
            print("❌ User or token not found")
            return False

        api_key = os.environ.get('KITE_API_KEY')
        access_token = user.kite_access_token

        print(f"\n1. Credentials:")
        print(f"   API Key: {api_key}")
        print(f"   Access Token: {access_token[:20]}...")

        # Initialize Kite client
        try:
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            print("   ✅ Kite client initialized")
        except Exception as e:
            print(f"   ❌ Failed to initialize: {e}")
            return False

        # Use EXACT same parameters as Postman
        instrument_token = 256265  # From your Postman request
        from_date = datetime(2024, 5, 1, 9, 15, 0)  # 2024-05-01 09:15:00
        to_date = datetime(2025, 5, 1, 15, 30, 0)   # 2025-05-01 15:30:00

        print(f"\n2. Request Parameters (EXACT match to Postman):")
        print(f"   Instrument Token: {instrument_token}")
        print(f"   From: {from_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   To: {to_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Interval: day")

        # Test profile first
        print(f"\n3. Testing profile API...")
        try:
            profile = kite.profile()
            print(f"   ✅ Profile API works: {profile.get('user_name')}")
        except Exception as e:
            print(f"   ❌ Profile API failed: {e}")
            return False

        # Test historical_data with EXACT Postman parameters
        print(f"\n4. Testing historical_data API with EXACT Postman params...")
        try:
            data = kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval='day'
            )

            print(f"   ✅ SUCCESS! Got {len(data)} candles")
            if data:
                print(f"   First candle: {data[0]}")
                print(f"   Last candle: {data[-1]}")
            return True

        except Exception as e:
            print(f"   ❌ Historical data API failed: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    try:
        success = test_exact_postman()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
