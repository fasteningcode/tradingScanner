#!/usr/bin/env python3
"""
Direct HTTP test to verify Kite historical data API access
"""
import sys
import os
import requests
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Instrument

def test_kite_direct():
    """Test Kite API with direct HTTP requests"""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("Direct Kite API HTTP Test")
        print("=" * 60)

        # Get user credentials
        user = User.query.get(1)
        if not user or not user.kite_access_token:
            print("❌ User or token not found")
            return False

        api_key = os.environ.get('KITE_API_KEY')
        access_token = user.kite_access_token

        print(f"\n1. Credentials:")
        print(f"   API Key: {api_key}")
        print(f"   Access Token: {access_token[:20]}...")
        print(f"   User ID: {user.kite_user_id}")

        # Get a test instrument
        test_inst = Instrument.query.filter_by(
            exchange='NSE',
            instrument_type='EQ'
        ).first()

        if not test_inst:
            print("❌ No instruments found")
            return False

        print(f"\n2. Test Instrument:")
        print(f"   Symbol: {test_inst.tradingsymbol}")
        print(f"   Token: {test_inst.instrument_token}")

        # Prepare request
        to_date = datetime.now()
        from_date = to_date - timedelta(days=7)

        url = f"https://api.kite.trade/instruments/historical/{test_inst.instrument_token}/day"

        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {api_key}:{access_token}"
        }

        params = {
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d")
        }

        print(f"\n3. HTTP Request:")
        print(f"   URL: {url}")
        print(f"   Headers: {headers}")
        print(f"   Params: {params}")

        # Make request
        print(f"\n4. Making request...")
        response = requests.get(url, headers=headers, params=params)

        print(f"   Status Code: {response.status_code}")
        print(f"   Response Headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ SUCCESS!")
            print(f"   Response keys: {data.keys()}")
            if 'data' in data and 'candles' in data['data']:
                candles = data['data']['candles']
                print(f"   Got {len(candles)} candles")
                if candles:
                    print(f"   First candle: {candles[0]}")
            return True
        else:
            print(f"   ❌ FAILED!")
            print(f"   Response: {response.text}")
            return False

if __name__ == '__main__':
    try:
        success = test_kite_direct()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
