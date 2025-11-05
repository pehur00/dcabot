#!/usr/bin/env python3
"""
GLM API Test Script for Trading Bot (via z.ai)
Tests GLM-4.6 API with real trading scenarios

Usage:
    export GLM_API_KEY="your_api_key_here"
    python test_glm_api.py
"""

import os
import sys
import json
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, Any


def fetch_live_market_data(symbol: str) -> Dict[str, Any]:
    """
    Fetch real-time market data from Binance API
    Returns technical indicators and price data
    """
    print(f"📡 Fetching live data for {symbol}...")

    try:
        # Binance API endpoints
        base_url = "https://api.binance.com/api/v3"

        # Get current price and 24h stats
        ticker_url = f"{base_url}/ticker/24hr?symbol={symbol}"
        ticker_response = requests.get(ticker_url, timeout=10)
        ticker_data = ticker_response.json()

        current_price = float(ticker_data['lastPrice'])
        volume_24h = float(ticker_data['volume'])
        price_change_24h = float(ticker_data['priceChangePercent'])

        # Get klines for EMA calculation (1m, 5m, 1h)
        def get_ema(interval: str, period: int) -> float:
            klines_url = f"{base_url}/klines?symbol={symbol}&interval={interval}&limit={period + 50}"
            klines_response = requests.get(klines_url, timeout=10)
            klines = klines_response.json()
            closes = [float(k[4]) for k in klines]  # Close prices

            # Calculate EMA
            df = pd.DataFrame({'close': closes})
            ema = df['close'].ewm(span=period, adjust=False).mean().iloc[-1]
            return float(ema)

        # Calculate EMAs
        ema20_1m = get_ema('1m', 20)
        ema50_5m = get_ema('5m', 50)
        ema100_1h = get_ema('1h', 100)

        # Calculate RSI (14 period on 1m)
        def calculate_rsi(interval: str = '1m', period: int = 14) -> float:
            klines_url = f"{base_url}/klines?symbol={symbol}&interval={interval}&limit={period + 50}"
            klines_response = requests.get(klines_url, timeout=10)
            klines = klines_response.json()
            closes = [float(k[4]) for k in klines]

            # Calculate RSI
            df = pd.DataFrame({'close': closes})
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi.iloc[-1])

        rsi = calculate_rsi()

        # Determine volume trend
        klines_5m = requests.get(f"{base_url}/klines?symbol={symbol}&interval=5m&limit=20", timeout=10).json()
        recent_volumes = [float(k[5]) for k in klines_5m[-5:]]
        older_volumes = [float(k[5]) for k in klines_5m[-10:-5]]
        avg_recent = sum(recent_volumes) / len(recent_volumes)
        avg_older = sum(older_volumes) / len(older_volumes)
        volume_trend = "INCREASING" if avg_recent > avg_older * 1.1 else "DECREASING" if avg_recent < avg_older * 0.9 else "STABLE"

        # Determine trend
        trend_parts = []
        if ema20_1m > ema50_5m:
            trend_parts.append("1m bullish")
        else:
            trend_parts.append("1m bearish")

        if ema50_5m > ema100_1h:
            trend_parts.append("5m bullish")
        else:
            trend_parts.append("5m bearish")

        if current_price > ema100_1h:
            trend_parts.append("above 1h EMA100")
        else:
            trend_parts.append("below 1h EMA100")

        trend = ", ".join(trend_parts)

        # Calculate 1h change
        klines_1h = requests.get(f"{base_url}/klines?symbol={symbol}&interval=1h&limit=2", timeout=10).json()
        price_1h_ago = float(klines_1h[-2][4])
        change_1h = ((current_price - price_1h_ago) / price_1h_ago) * 100

        print(f"✅ Live data fetched: ${current_price:,.2f}")

        return {
            "symbol": symbol,
            "current_price": current_price,
            "ema20_1m": ema20_1m,
            "ema50_5m": ema50_5m,
            "ema100_1h": ema100_1h,
            "rsi": round(rsi, 1),
            "volume_trend": volume_trend,
            "trend": trend,
            "change_24h": round(price_change_24h, 2),
            "change_1h": round(change_1h, 2),
            "fear_greed": "N/A (use sentiment API if needed)",
            "position": "None"
        }

    except Exception as e:
        print(f"❌ Error fetching live data: {e}")
        return None


class GLMTradingTest:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GLM_API_KEY")
        if not self.api_key:
            print("❌ ERROR: GLM_API_KEY not found!")
            print("\nPlease set your API key:")
            print("  export GLM_API_KEY='your_key_here'")
            sys.exit(1)

        self.base_url = "https://api.z.ai/api/paas/v4/chat/completions"
        # Choose model: "glm-4.5-flash" (FREE but slower) or "glm-4.5-air" ($1.20/month, faster)
        self.model = os.getenv("GLM_MODEL", "glm-4.5-air")  # Default to Air for speed

    def test_connection(self) -> bool:
        """Test if API key works"""
        print(f"🔌 Testing GLM API connection...")
        print(f"📊 Model: {self.model}")

        try:
            response = self._call_api(
                messages=[{"role": "user", "content": "Hello, respond with 'OK'"}],
                temperature=0.1
            )

            if response and "OK" in response.get("content", ""):
                print("✅ Connection successful!")
                return True
            else:
                print("⚠️  Connection works but unexpected response")
                return False

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def _call_api(self, messages: list, temperature: float = 0.3) -> Dict[str, Any]:
        """Call GLM API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2000  # Increased to avoid truncation
        }

        response = requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=90  # Increased for free tier queuing
        )

        if response.status_code != 200:
            raise Exception(f"API Error {response.status_code}: {response.text}")

        result = response.json()

        return {
            "content": result["choices"][0]["message"]["content"],
            "usage": result.get("usage", {}),
            "model": result.get("model", "unknown")
        }

    def test_trading_scenario(self, scenario_name: str, market_data: Dict) -> Dict[str, Any]:
        """Test GLM with a trading scenario"""
        print(f"\n{'='*60}")
        print(f"📊 Testing Scenario: {scenario_name}")
        print(f"{'='*60}")

        # Build the prompt
        system_prompt = """You are an expert cryptocurrency trading assistant.

Analyze the provided market data and make a trading decision.

IMPORTANT: Keep reasoning concise (2-3 sentences max).

Output Format (JSON only, no markdown):
{
  "decision": "HOLD|BUY|SELL",
  "confidence": 0-100,
  "reasoning": "brief 2-3 sentence explanation",
  "risk_level": "LOW|MEDIUM|HIGH",
  "stop_loss": price_level,
  "take_profit": price_level
}"""

        user_prompt = f"""
**Market Analysis Request**

Symbol: {market_data['symbol']}
Current Price: ${market_data['current_price']}
Current Position: {market_data.get('position', 'None')}

**Technical Indicators:**
- EMA20 (1min): ${market_data['ema20_1m']} (Price is {"ABOVE" if market_data['current_price'] > market_data['ema20_1m'] else "BELOW"})
- EMA50 (5min): ${market_data['ema50_5m']}
- EMA100 (1h): ${market_data['ema100_1h']}
- RSI (14): {market_data['rsi']}
- Volume Trend: {market_data['volume_trend']}

**Sentiment:**
- Fear & Greed Index: {market_data['fear_greed']}
- Market Trend: {market_data['trend']}

**Recent Price Action:**
- 24h Change: {market_data['change_24h']}%
- 1h Change: {market_data['change_1h']}%

Should I BUY, SELL, or HOLD? Provide your analysis in JSON format.
"""

        try:
            print("\n⏳ Calling GLM API...")
            start_time = datetime.now()

            response = self._call_api(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            elapsed = (datetime.now() - start_time).total_seconds()

            print(f"✅ Response received in {elapsed:.2f}s")

            # Parse JSON from response
            content = response["content"]

            # Try to extract JSON if wrapped in markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            # Try to parse JSON, handle truncation
            try:
                decision = json.loads(content)
            except json.JSONDecodeError as e:
                # If JSON is truncated, try to fix it
                print(f"⚠️  JSON truncated, attempting to fix...")

                # Add missing closing braces
                if content.count("{") > content.count("}"):
                    content = content + "}"

                # Try to extract what we have and add placeholder reasoning
                try:
                    # Find the last complete field before truncation
                    lines = content.split('\n')
                    fixed_lines = []
                    for line in lines:
                        if '"reasoning"' in line and not line.strip().endswith(',') and not line.strip().endswith('"'):
                            # Truncated reasoning, close it
                            line = line.rstrip() + '..."'
                        fixed_lines.append(line)

                    content = '\n'.join(fixed_lines)
                    if not content.endswith('}'):
                        content = content + '\n}'

                    decision = json.loads(content)
                    decision['reasoning'] = decision.get('reasoning', '') + ' [Response truncated, increase max_tokens]'
                except:
                    # If still fails, create minimal response
                    print(f"❌ Cannot parse JSON. Raw content:\n{content}")
                    raise e

            # Display results
            print("\n" + "="*60)
            print("🤖 GLM TRADING DECISION")
            print("="*60)
            print(f"Decision:    {decision.get('decision', 'N/A')}")
            print(f"Confidence:  {decision.get('confidence', 'N/A')}/100")
            print(f"Risk Level:  {decision.get('risk_level', 'N/A')}")
            print(f"Stop Loss:   ${decision.get('stop_loss', 'N/A')}")
            print(f"Take Profit: ${decision.get('take_profit', 'N/A')}")
            print(f"\nReasoning:")
            print(f"{decision.get('reasoning', 'N/A')}")
            print("="*60)

            # Usage stats
            usage = response.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            # Calculate cost based on model
            if "flash" in self.model.lower():
                cost = 0.0  # FREE!
            elif "air" in self.model.lower() and "airx" not in self.model.lower():
                # GLM-4.5-Air: $0.2/M input + $1.1/M output
                cost = (input_tokens * 0.2 / 1_000_000) + (output_tokens * 1.1 / 1_000_000)
            else:
                # Default GLM-4.6 pricing
                cost = (input_tokens * 0.6 / 1_000_000) + (output_tokens * 2.2 / 1_000_000)

            print(f"\n💰 API Usage:")
            print(f"   Input Tokens:  {input_tokens}")
            print(f"   Output Tokens: {output_tokens}")
            print(f"   Total Cost:    ${cost:.6f}")
            print(f"   Response Time: {elapsed:.2f}s")

            return {
                "success": True,
                "decision": decision,
                "cost": cost,
                "elapsed": elapsed,
                "usage": usage
            }

        except json.JSONDecodeError as e:
            print(f"\n❌ Failed to parse JSON response: {e}")
            print(f"Raw response:\n{response['content']}")
            return {"success": False, "error": "JSON parse error"}

        except Exception as e:
            print(f"\n❌ Error: {e}")
            return {"success": False, "error": str(e)}


def main():
    print("="*60)
    print("🤖 GLM API Trading Bot Test (via z.ai)")
    print("="*60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Initialize tester
    tester = GLMTradingTest()

    # Test connection
    if not tester.test_connection():
        print("\n❌ Connection test failed. Please check your API key.")
        sys.exit(1)

    # Test Scenario 1: BTCUSDT with LIVE data
    print("\n" + "="*60)
    print("🔴 LIVE TEST: Fetching real-time market data...")
    print("="*60)

    scenario1 = fetch_live_market_data("BTCUSDT")
    if not scenario1:
        print("❌ Failed to fetch live data for BTCUSDT. Exiting.")
        sys.exit(1)

    result1 = tester.test_trading_scenario("BTCUSDT (LIVE)", scenario1)

    # Test Scenario 2: SOLUSDT with LIVE data
    print("\n" + "="*60)
    input("\nPress Enter to test next scenario (SOLUSDT LIVE)...")

    scenario2 = fetch_live_market_data("SOLUSDT")
    if not scenario2:
        print("❌ Failed to fetch live data for SOLUSDT. Exiting.")
        sys.exit(1)

    result2 = tester.test_trading_scenario("SOLUSDT (LIVE)", scenario2)

    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)

    if result1.get("success") and result2.get("success"):
        total_cost = result1.get("cost", 0) + result2.get("cost", 0)
        avg_time = (result1.get("elapsed", 0) + result2.get("elapsed", 0)) / 2

        print(f"✅ Both scenarios completed successfully!")
        print(f"\nTotal API Cost: ${total_cost:.6f}")
        print(f"Average Response Time: {avg_time:.2f}s")
        print(f"\n💡 Monthly Cost Estimate:")
        monthly_cost = total_cost * 1500
        print(f"   At 3,000 calls/month: ${monthly_cost:.2f}")
        savings = 150 - monthly_cost
        print(f"   vs Claude ($150/month): Save ${savings:.2f}/month! 🎉")

        # Compare decisions
        print(f"\n🎯 GLM Trading Decisions:")
        print(f"   BTC (Bullish): {result1['decision'].get('decision', 'N/A')} @ {result1['decision'].get('confidence', 'N/A')}% confidence")
        print(f"   SOL (Crash):   {result2['decision'].get('decision', 'N/A')} @ {result2['decision'].get('confidence', 'N/A')}% confidence")

        print(f"\n✅ GLM API is working and making trading decisions!")
        print(f"\nNext Steps:")
        print(f"  1. Review the decision quality above")
        print(f"  2. If satisfied, integrate into trading bot")
        print(f"  3. Build data pipeline for real-time market data")
        print(f"  4. Deploy MVP for paper trading")

    else:
        print("⚠️  Some tests failed. Check errors above.")

    print("="*60)


if __name__ == "__main__":
    main()
