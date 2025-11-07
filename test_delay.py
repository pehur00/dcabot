#!/usr/bin/env python3
"""
Test API key activation delay
Usage: python3 test_delay.py <API_KEY> <API_SECRET>
"""

import time
import sys
from simple_balance_check import make_phemex_api_call

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 test_delay.py <API_KEY> <API_SECRET>")
        sys.exit(1)

    api_key = sys.argv[1]
    api_secret = sys.argv[2]

    print("🕐 Testing API key activation delay...")
    print("=" * 50)

    # Test 6 times over 15 minutes
    for i in range(6):
        print(f"\n⏰ Test #{i+1} at {time.strftime('%H:%M:%S')}")

        balance_info = make_phemex_api_call(api_key, api_secret)

        if balance_info:
            available = balance_info.get('accountBalanceRv', '0')
            print(f"📊 Available balance: {available} USDT")

            if available != '0' and available != 'NOT_FOUND':
                print("✅ API key is ACTIVE and has balance!")
                break
            else:
                print("⏳ API key still activating or no balance...")
        else:
            print("❌ API call failed")

        if i < 5:  # Don't sleep after last test
            print("⏱️  Waiting 2 minutes...")
            time.sleep(120)  # 2 minutes

if __name__ == "__main__":
    main()