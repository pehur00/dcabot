#!/usr/bin/env python3
"""
GLM API Test Script for Trading Bot
Tests z.ai (Zhipu GLM-4.5) API with real trading scenarios

Usage:
    export ZHIPU_API_KEY="your_api_key_here"
    python test_glm_api.py
"""

import os
import sys
import json
import requests
from datetime import datetime
from typing import Dict, Any


class GLMTradingTest:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ZHIPU_API_KEY")
        if not self.api_key:
            print("❌ ERROR: ZHIPU_API_KEY not found!")
            print("\nPlease set your API key:")
            print("  export ZHIPU_API_KEY='your_key_here'")
            sys.exit(1)

        self.base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        self.model = "glm-4.6"  # Latest flagship model (Sept 2025)

    def test_connection(self) -> bool:
        """Test if API key works"""
        print("🔌 Testing GLM API connection...")

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
            "max_tokens": 1500
        }

        response = requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=30
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

Output Format (JSON only, no markdown):
{
  "decision": "HOLD|BUY|SELL",
  "confidence": 0-100,
  "reasoning": "detailed explanation",
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

            decision = json.loads(content)

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

            # Calculate cost (GLM-4: $0.11/M input, $0.28/M output)
            cost = (input_tokens * 0.11 / 1_000_000) + (output_tokens * 0.28 / 1_000_000)

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
    print("🤖 GLM API Trading Bot Test")
    print("="*60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Initialize tester
    tester = GLMTradingTest()

    # Test connection
    if not tester.test_connection():
        print("\n❌ Connection test failed. Please check your API key.")
        sys.exit(1)

    # Test Scenario 1: BTCUSDT Bullish Setup
    scenario1 = {
        "symbol": "BTCUSDT",
        "current_price": 42500.00,
        "position": "None",
        "ema20_1m": 42480,
        "ema50_5m": 42350,
        "ema100_1h": 42200,
        "rsi": 65,
        "volume_trend": "INCREASING",
        "fear_greed": "72 (GREED)",
        "trend": "BULLISH (all EMAs aligned up)",
        "change_24h": +2.5,
        "change_1h": +0.8
    }

    result1 = tester.test_trading_scenario("BTC Bullish Setup", scenario1)

    # Test Scenario 2: SOLUSDT Crash (Nov 1-4 example)
    print("\n" + "="*60)
    input("\nPress Enter to test next scenario (SOLUSDT Crash)...")

    scenario2 = {
        "symbol": "SOLUSDT",
        "current_price": 165.00,
        "position": "0.5 SOL @ $185 (Underwater -10.8%)",
        "ema20_1m": 166,
        "ema50_5m": 172,
        "ema100_1h": 180,
        "rsi": 28,
        "volume_trend": "HIGH (panic selling)",
        "fear_greed": "25 (FEAR)",
        "trend": "STRONG DOWNTREND (all EMAs pointing down)",
        "change_24h": -12.5,
        "change_1h": -3.2
    }

    result2 = tester.test_trading_scenario("SOL Crash Scenario", scenario2)

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
        print(f"   At 3,000 calls/month: ${total_cost * 1500:.2f}")
        print(f"   (That's 97% cheaper than Claude at $150/month!)")

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
