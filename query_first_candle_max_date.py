#!/usr/bin/env python3
"""
Query historical_data table and find the maximum date among first candles
"""
import sqlite3
import json
from datetime import datetime

# Connect to the database
conn = sqlite3.connect('instance/app.db')
cursor = conn.cursor()

# Query all historical_data records
cursor.execute("SELECT id, tradingsymbol, interval, candlestick_data FROM historical_data")

first_candle_dates = []
max_date = None
max_date_record = None

print("Processing historical_data records...\n")
print(f"{'ID':<6} {'Symbol':<15} {'Interval':<10} {'First Candle Date':<20}")
print("-" * 60)

for row in cursor.fetchall():
    record_id, tradingsymbol, interval, candlestick_data = row

    try:
        # Parse the JSON candlestick data
        candles = json.loads(candlestick_data)

        if candles and len(candles) > 0:
            # Get the first candle
            first_candle = candles[0]
            first_date_str = first_candle.get('date')

            if first_date_str:
                # Parse the date
                first_date = datetime.strptime(first_date_str, '%Y-%m-%d')
                first_candle_dates.append({
                    'id': record_id,
                    'tradingsymbol': tradingsymbol,
                    'interval': interval,
                    'date': first_date,
                    'date_str': first_date_str
                })

                print(f"{record_id:<6} {tradingsymbol:<15} {interval:<10} {first_date_str:<20}")

                # Track the maximum date
                if max_date is None or first_date > max_date:
                    max_date = first_date
                    max_date_record = {
                        'id': record_id,
                        'tradingsymbol': tradingsymbol,
                        'interval': interval,
                        'date_str': first_date_str
                    }
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"Error processing record {record_id} ({tradingsymbol}): {e}")

conn.close()

# Print summary
print("\n" + "=" * 60)
print(f"\nTotal records processed: {len(first_candle_dates)}")

if max_date_record:
    print(f"\n🎯 MAXIMUM DATE among first candles:")
    print(f"   Date: {max_date_record['date_str']}")
    print(f"   Record ID: {max_date_record['id']}")
    print(f"   Symbol: {max_date_record['tradingsymbol']}")
    print(f"   Interval: {max_date_record['interval']}")
else:
    print("\nNo valid dates found.")
