#!/usr/bin/env python3
"""
Simple Phemex Balance Check - Just the API call we need
Usage: python3 simple_balance_check.py <API_KEY> <API_SECRET>
"""

import time
import hmac
import hashlib
import requests
import json
import sys

def make_phemex_api_call(api_key, api_secret):
    """Make the exact same API call as PhemexClient.get_account_balance()"""

    # Configuration (same as PhemexClient)
    base_url = "https://api.phemex.com"  # Mainnet
    endpoint = "/g-accounts/positions"
    method = "GET"
    params = {"currency": "USDT"}

    try:
        # Build authentication (same as PhemexClient._send_request)
        expiry = str(int(time.time()) + 60)
        query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        message = endpoint + query_string + expiry

        # Generate signature
        signature = hmac.new(
            api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Set headers (same as PhemexClient)
        headers = {
            'x-phemex-request-signature': signature,
            'x-phemex-request-expiry': expiry,
            'x-phemex-access-token': api_key,
            'Content-Type': 'application/json'
        }

        # Make API request
        url = f"{base_url}{endpoint}?{query_string}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()

            # Just print the full response and balance info
            print("📡 FULL API RESPONSE:")
            print(json.dumps(data, indent=2))

            # Extract balance info (same as PhemexClient)
            balance_info = data['data']['account']

            print("\n" + "="*80)
            print("💰 BALANCE INFO:")
            print(f"Available Balance (accountBalanceRv): {balance_info.get('accountBalanceRv', 'NOT_FOUND')}")
            print(f"Used Balance (totalUsedBalanceRv): {balance_info.get('totalUsedBalanceRv', 'NOT_FOUND')}")
            print(f"Bonus Balance (bonusBalanceRv): {balance_info.get('bonusBalanceRv', 'NOT_FOUND')}")
            print(f"User ID: {balance_info.get('userID', 'NOT_FOUND')}")
            print(f"Account ID: {balance_info.get('accountId', 'NOT_FOUND')}")
            print(f"Status: {balance_info.get('status', 'NOT_FOUND')}")
            print(f"User Mode: {balance_info.get('userMode', 'NOT_FOUND')}")

            return balance_info

        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    print("🚀 Simple Phemex Balance Check")
    print("=" * 50)

    # Check command line arguments
    if len(sys.argv) != 3:
        print("❌ Usage: python3 simple_balance_check.py <API_KEY> <API_SECRET>")
        print("\nExample:")
        print('   python3 simple_balance_check.py "your_api_key" "your_api_secret"')
        sys.exit(1)

    api_key = sys.argv[1]
    api_secret = sys.argv[2]

    # Validate credentials
    if not api_key or not api_secret:
        print("❌ API key and secret cannot be empty!")
        sys.exit(1)

    # Make the API call
    balance_info = make_phemex_api_call(api_key, api_secret)

    if balance_info:
        print("\n✅ API call completed successfully!")

        # Simple interpretation
        available = balance_info.get('accountBalanceRv', '0')
        if available != '0' and available != 'NOT_FOUND':
            print(f"✅ Available balance: {available} USDT")
        else:
            print("❌ No available balance found")

    else:
        print("\n❌ API call failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()