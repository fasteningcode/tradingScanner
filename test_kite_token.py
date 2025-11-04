#!/usr/bin/env python3
"""
Test script to verify Kite token is valid and working
"""
import sys
import os
from app import create_app, db
from app.models import User
from kiteconnect import KiteConnect

def test_kite_token():
    """Test that Kite token works correctly"""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("Testing Kite Token")
        print("=" * 60)

        # Get user
        user = User.query.get(1)
        if not user:
            print("❌ User not found")
            return False

        print(f"\n1. User: {user.username}")
        print(f"   Kite Connected: {user.kite_connected}")
        print(f"   Kite User ID: {user.kite_user_id}")
        print(f"   Token Expires: {user.kite_access_token_expires}")
        print(f"   Token Valid: {user.is_kite_token_valid()}")

        if not user.kite_access_token:
            print("❌ No access token")
            return False

        # Test Kite client initialization
        print("\n2. Testing Kite client initialization...")
        try:
            api_key = os.environ.get('KITE_API_KEY')
            print(f"   API Key: {api_key[:10]}...")

            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(user.kite_access_token)
            print("   ✅ Kite client initialized")
        except Exception as e:
            print(f"   ❌ Failed to initialize: {e}")
            return False

        # Test profile API
        print("\n3. Testing profile API...")
        try:
            profile = kite.profile()
            print(f"   Name: {profile.get('user_name')}")
            print(f"   Email: {profile.get('email')}")
            print(f"   Broker: {profile.get('broker')}")
            print("   ✅ Profile API works")
        except Exception as e:
            print(f"   ❌ Profile API failed: {e}")
            return False

        # Test historical_data API with a single stock
        print("\n4. Testing historical_data API...")
        try:
            from datetime import datetime, timedelta
            from kiteconnect.exceptions import InputException

            # Get a test instrument
            from app.models import Instrument
            test_inst = Instrument.query.filter_by(
                exchange='NSE',
                instrument_type='EQ'
            ).first()

            if not test_inst:
                print("   ⚠️  No instruments in database")
                return False

            print(f"   Testing with: {test_inst.tradingsymbol} (token: {test_inst.instrument_token})")

            # Try to fetch last 7 days of data
            to_date = datetime.now()
            from_date = to_date - timedelta(days=7)

            print(f"   Date range: {from_date.date()} to {to_date.date()}")

            data = kite.historical_data(
                instrument_token=test_inst.instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval='day'
            )

            print(f"   ✅ Got {len(data)} candles")
            if data:
                print(f"   First candle: {data[0]}")
        except InputException as e:
            if "invalid token" in str(e).lower():
                print(f"   ❌ Historical data API failed: {e}")
                print("\n   ⚠️  IMPORTANT:")
                print("   The 'invalid token' error for historical data usually means:")
                print("   1. Your Kite Connect app doesn't have historical data permissions")
                print("   2. You need to subscribe to Kite Connect Historical Data API")
                print("   3. Check your Kite Connect app settings at https://developers.kite.trade/apps")
                print("   4. Ensure 'Historical Data' permission is enabled for your app")
                return False
            else:
                print(f"   ❌ Historical data API failed: {e}")
                import traceback
                traceback.print_exc()
                return False
        except Exception as e:
            print(f"   ❌ Historical data API failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        print("\n" + "=" * 60)
        print("All tests passed! ✅")
        print("=" * 60)
        return True

if __name__ == '__main__':
    try:
        success = test_kite_token()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
