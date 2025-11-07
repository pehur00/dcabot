#!/usr/bin/env python3
"""
Phemex Balance Checker Script
Usage: python3 check_balance.py <API_KEY> <API_SECRET>

Example: python3 check_balance.py "your_api_key_here" "your_api_secret_here"
"""

import time
import hmac
import hashlib
import requests
import json
import sys

def check_phemex_balance(api_key, api_secret):
    """Check Phemex account balance and positions"""

    # Configuration
    base_url = "https://api.phemex.com"  # Mainnet
    endpoint = "/g-accounts/positions"
    method = "GET"
    params = {"currency": "USDT"}

    try:
        # Build authentication
        expiry = str(int(time.time()) + 60)
        query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        message = endpoint + query_string + expiry

        # Generate signature
        signature = hmac.new(
            api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Set headers
        headers = {
            'x-phemex-request-signature': signature,
            'x-phemex-request-expiry': expiry,
            'x-phemex-access-token': api_key,
            'Content-Type': 'application/json'
        }

        # Make API request
        url = f"{base_url}{endpoint}?{query_string}"
        print(f"🔍 Checking Phemex balance...")
        print(f"📡 API URL: {url}")
        print("-" * 50)

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()

            # Print full API response first
            print("📡 FULL API RESPONSE:")
            print(json.dumps(data, indent=2))
            print("\n" + "=" * 80 + "\n")

            # Parse account information
            account = data['data']['account']
            available_balance = float(account['accountBalanceRv'])
            used_balance = float(account['totalUsedBalanceRv'])

            # Display results
            print("💰 BALANCE INFORMATION")
            print(f"Available Balance: ${available_balance:,.2f} USDT")
            print(f"Used Balance:      ${used_balance:,.2f} USDT")
            print(f"Total Balance:     ${(available_balance + used_balance):,.2f} USDT")
            print(f"Account ID:        {account['accountId']}")
            print(f"User ID:           {account['userID']}")

            # Show position summary
            positions = data['data']['positions']
            active_positions = [p for p in positions if float(p['sizeRq']) != 0]

            print("\n📊 POSITIONS SUMMARY")
            print(f"Total positions: {len(active_positions)}")
            print(f"Inactive positions: {len(positions) - len(active_positions)}")

            if active_positions:
                print("\n🔥 ACTIVE POSITIONS:")
                for pos in active_positions[:10]:  # Show first 10
                    symbol = pos['symbol']
                    size = float(pos['sizeRq'])
                    side = pos['posSide']
                    leverage = pos['leverageRr'].replace('-', '')
                    unrealized_pnl = float(pos['unRealisedPnlRv'])

                    pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
                    print(f"  {symbol:12} | {side:5} | Size: {size:8.2f} | {leverage:3}x | {pnl_emoji} PnL: ${unrealized_pnl:+.2f}")

                if len(active_positions) > 10:
                    print(f"  ... and {len(active_positions) - 10} more positions")

            # AI Bot Recommendations
            print("\n🤖 AI BOT STATUS:")
            if available_balance > 100:
                print("✅ Good balance available for AI trading")
                print(f"   Can fund approximately {int(available_balance / 50)} AI bot positions")
            elif available_balance > 50:
                print("⚠️  Limited balance available for AI trading")
                print(f"   Can fund approximately {int(available_balance / 50)} AI bot positions")
            elif available_balance > 0:
                print("❌ Very low balance - consider adding funds or closing positions")
            else:
                print("❌ No available balance - add funds or close some positions to enable AI trading")

            return data

        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Network Error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    print("🚀 Phemex Balance Checker")
    print("=" * 50)

    # Check command line arguments
    if len(sys.argv) != 3:
        print("❌ Usage: python3 check_balance.py <API_KEY> <API_SECRET>")
        print("\nExample:")
        print('   python3 check_balance.py "your_api_key" "your_api_secret"')
        print("\nMake sure to quote your credentials if they contain special characters.")
        sys.exit(1)

    api_key = sys.argv[1]
    api_secret = sys.argv[2]

    # Validate credentials aren't empty
    if not api_key or not api_secret:
        print("❌ API key and secret cannot be empty!")
        sys.exit(1)

    # Check balance multiple times to see if it fluctuates
    print("🔄 Checking balance 3 times to detect fluctuations...")

    balance_data = None
    for i in range(3):
        print(f"\n--- CHECK #{i+1} at {time.strftime('%H:%M:%S')} ---")
        balance_data = check_phemex_balance(api_key, api_secret)

        if i < 2:  # Don't sleep after last check
            print("⏳ Waiting 3 seconds...")
            time.sleep(3)

    if balance_data:
        print("\n✅ Balance check completed successfully!")

        # Additional analysis
        account = balance_data['data']['account']
        available_balance = float(account['accountBalanceRv'])

        print("\n🎯 MARTINGALE STRATEGY COMPATIBILITY:")
        if available_balance > 10:
            print("✅ Martingale strategy can run (has balance)")
            proportion_of_balance = 0.006  # From Martingale CONFIG
            initial_position = available_balance * proportion_of_balance
            print(f"   Initial position size: ${initial_position:.2f} ({proportion_of_balance*100:.1f}%)")
        else:
            print("❌ Martingale strategy may face balance issues")

    else:
        print("\n❌ Balance check failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()