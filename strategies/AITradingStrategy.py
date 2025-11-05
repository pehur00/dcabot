"""
AI Trading Strategy
Uses LLM models (GLM, DeepSeek, Claude) to make trading decisions
based on comprehensive market analysis
"""

import json
import time
import requests
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


class AITradingStrategy:
    """
    AI-powered trading strategy using LLM for decision-making

    Supports multiple models:
    - GLM-4.5-Air (z.ai)
    - GLM-4.5-Flash (z.ai)
    - DeepSeek-Chat
    - Claude-3.5-Sonnet
    """

    def __init__(self, bot_config: Dict, model_config: Dict, api_key: str):
        """
        Initialize AI trading strategy

        Args:
            bot_config: Bot configuration (symbol, leverage, max_position_size, etc.)
            model_config: Model configuration (endpoint, model_id, pricing, etc.)
            api_key: Decrypted API key for the AI model
        """
        self.bot_config = bot_config
        self.model_config = model_config
        self.api_key = api_key

        # Model details
        self.api_endpoint = model_config['api_endpoint']
        self.model_identifier = model_config['model_identifier']
        self.provider = model_config['provider']

        # Pricing
        self.cost_per_1m_input = float(model_config.get('cost_per_1m_input', 0))
        self.cost_per_1m_output = float(model_config.get('cost_per_1m_output', 0))

    def get_trading_decision(self, market_data: Dict) -> Dict[str, Any]:
        """
        Get trading decision from AI model

        Args:
            market_data: Comprehensive market data from MarketDataFetcher

        Returns:
            Dict with decision, confidence, reasoning, etc.
        """
        try:
            logger.info(f"Getting AI decision for {market_data['symbol']} using {self.model_config['name']}")

            # Build enriched prompt
            prompt = self.build_enriched_prompt(market_data)

            # Call AI model
            start_time = time.time()
            response = self._call_ai_api(prompt)
            response_time_ms = int((time.time() - start_time) * 1000)

            # Parse decision from response
            decision = self._parse_ai_response(response)

            # Add metadata
            decision['response_time_ms'] = response_time_ms
            decision['input_tokens'] = response.get('usage', {}).get('prompt_tokens', 0)
            decision['output_tokens'] = response.get('usage', {}).get('completion_tokens', 0)
            decision['api_cost'] = self._calculate_cost(
                decision['input_tokens'],
                decision['output_tokens']
            )
            decision['model_name'] = self.model_config['name']

            logger.info(
                f"AI Decision: {decision['decision']} "
                f"(confidence: {decision['confidence']}%, "
                f"cost: ${decision['api_cost']:.6f})"
            )

            return decision

        except Exception as e:
            logger.error(f"Error getting AI decision: {e}")
            raise

    def build_enriched_prompt(self, market_data: Dict) -> str:
        """
        Build comprehensive prompt with all available data sources

        Includes:
        - Technical indicators
        - Sentiment data
        - Current position info
        - Trading rules
        """
        symbol = market_data['symbol']
        price = market_data['current_price']

        # Format technical analysis section
        technical_section = f"""**TECHNICAL ANALYSIS:**
Symbol: {symbol}
Current Price: ${price:,.2f}

**Moving Averages:**
- EMA20 (1min): ${market_data['ema20_1m']:,.2f} (Price is {'ABOVE' if price > market_data['ema20_1m'] else 'BELOW'})
- EMA50 (5min): ${market_data['ema50_5m']:,.2f}
- EMA100 (1h): ${market_data['ema100_1h']:,.2f}

**Momentum Indicators:**
- RSI(14): {market_data['rsi']} ({'OVERSOLD' if market_data['rsi'] < 30 else 'OVERBOUGHT' if market_data['rsi'] > 70 else 'NEUTRAL'})
- Volume Trend: {market_data['volume_trend']}
- Trend: {market_data['trend']}

**Price Changes:**
- 24h: {market_data['change_24h']:+.2f}%
- 1h: {market_data['change_1h']:+.2f}%"""

        # Format sentiment section with all sources
        sentiment_parts = []

        # Fear & Greed Index
        fear_greed = market_data.get('fear_greed_index')
        if fear_greed is not None:
            sentiment_parts.append(f"- Fear & Greed Index: {fear_greed}/100")

        # Social sentiment (Twitter/LunarCrush)
        social = market_data.get('social_sentiment')
        if social:
            sentiment_parts.append(f"- Social Media: {social}")

        # Reddit sentiment
        reddit = market_data.get('reddit_sentiment')
        if reddit:
            sentiment_parts.append(f"- Reddit: {reddit}")

        # News headlines
        news = market_data.get('news_headlines', [])
        if news:
            sentiment_parts.append(f"- Recent News ({len(news)} headlines):")
            for headline in news[:3]:
                sentiment_parts.append(f"  • {headline}")

        sentiment_text = "\n".join(sentiment_parts) if sentiment_parts else "Limited sentiment data available"

        sentiment_section = f"""
**MARKET SENTIMENT:**
{sentiment_text}"""

        # Format position section
        position_section = f"""
**CURRENT POSITION:**
{market_data.get('current_position', 'None')}"""

        # Trading rules section
        rules_section = f"""
**TRADING RULES:**
- Only {self.bot_config['side']} positions allowed
- Max position size: {self.bot_config['max_position_size'] * 100}% of balance
- Leverage: {self.bot_config['leverage']}x
- Always set stop-loss (2% from entry)
- Risk management is critical"""

        # Build full prompt
        prompt = f"""You are an expert cryptocurrency trading AI assistant. Analyze ALL available data sources and make a trading decision.

{technical_section}

{sentiment_section}

{position_section}

{rules_section}

**YOUR TASK:**
Based on the comprehensive analysis above:

1. **Technical Analysis:** What do the EMAs, RSI, and volume tell you?
2. **Sentiment Analysis:** How does market sentiment influence your decision?
3. **Risk Assessment:** What are the key risks in this trade?
4. **Decision:** BUY, SELL, or HOLD?

**IMPORTANT:**
- Keep reasoning concise but insightful (3-4 sentences)
- Consider BOTH technical AND sentiment factors
- Be conservative with confidence scores
- Set realistic stop-loss and take-profit levels

**Output Format (JSON only, no markdown):**
{{
  "decision": "BUY|SELL|HOLD",
  "confidence": 75,
  "reasoning": "Brief 3-4 sentence explanation covering technical signals, sentiment factors, and key risks",
  "risk_level": "LOW|MEDIUM|HIGH",
  "stop_loss": {price * 0.98:.2f},
  "take_profit": {price * 1.03:.2f}
}}

Respond with ONLY the JSON, no other text."""

        return prompt

    def _call_ai_api(self, prompt: str) -> Dict:
        """
        Call the AI model API

        Handles different provider formats (z.ai, deepseek, anthropic)
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Build payload (OpenAI-compatible format for z.ai and DeepSeek)
        if self.provider in ['z.ai', 'deepseek', 'openai']:
            payload = {
                "model": self.model_identifier,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert cryptocurrency trading AI. Respond with JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 2000
            }
        elif self.provider == 'anthropic':
            # Claude API format (different from OpenAI)
            headers["x-api-key"] = self.api_key
            headers["anthropic-version"] = "2023-06-01"
            del headers["Authorization"]

            payload = {
                "model": self.model_identifier,
                "max_tokens": 2000,
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        # Make API call
        try:
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=payload,
                timeout=90
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            raise Exception(f"API timeout after 90s ({self.model_config['name']})")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"API error {response.status_code}: {response.text}")
        except Exception as e:
            raise Exception(f"Unexpected API error: {e}")

    def _parse_ai_response(self, response: Dict) -> Dict[str, Any]:
        """
        Parse AI response and extract decision

        Handles different response formats from different providers
        """
        try:
            # Extract content based on provider
            if self.provider in ['z.ai', 'deepseek', 'openai']:
                content = response['choices'][0]['message']['content']
            elif self.provider == 'anthropic':
                content = response['content'][0]['text']
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            # Parse JSON
            try:
                decision = json.loads(content)
            except json.JSONDecodeError as e:
                # Try to fix truncated JSON
                logger.warning(f"JSON parse error, attempting to fix: {e}")
                decision = self._fix_truncated_json(content)

            # Validate required fields
            required_fields = ['decision', 'confidence', 'reasoning', 'risk_level', 'stop_loss', 'take_profit']
            for field in required_fields:
                if field not in decision:
                    raise ValueError(f"Missing required field: {field}")

            # Validate decision value
            if decision['decision'] not in ['BUY', 'SELL', 'HOLD']:
                raise ValueError(f"Invalid decision: {decision['decision']}")

            # Validate confidence range
            if not (0 <= decision['confidence'] <= 100):
                logger.warning(f"Confidence out of range: {decision['confidence']}, clamping to 0-100")
                decision['confidence'] = max(0, min(100, decision['confidence']))

            return decision

        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            logger.debug(f"Raw response: {response}")
            raise

    def _fix_truncated_json(self, content: str) -> Dict:
        """Attempt to fix truncated JSON response"""
        # Add missing closing braces
        if content.count("{") > content.count("}"):
            content = content + "}"

        # Try to extract what we have
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
        decision['reasoning'] = decision.get('reasoning', '') + ' [Response truncated]'

        return decision

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate API cost for this call"""
        input_cost = (input_tokens / 1_000_000) * self.cost_per_1m_input
        output_cost = (output_tokens / 1_000_000) * self.cost_per_1m_output
        return input_cost + output_cost


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Mock bot config
    bot_config = {
        "symbol": "BTCUSDT",
        "side": "Long",
        "leverage": 5,
        "max_position_size": 0.03
    }

    # Mock model config
    model_config = {
        "name": "GLM-4.5-Air",
        "provider": "z.ai",
        "api_endpoint": "https://api.z.ai/api/paas/v4/chat/completions",
        "model_identifier": "glm-4.5-air",
        "cost_per_1m_input": 0.20,
        "cost_per_1m_output": 1.10
    }

    # Mock API key (replace with real key for testing)
    api_key = "your_api_key_here"

    # Mock market data
    market_data = {
        "symbol": "BTCUSDT",
        "current_price": 68500.00,
        "ema20_1m": 68450,
        "ema50_5m": 68300,
        "ema100_1h": 68000,
        "rsi": 65,
        "volume_trend": "INCREASING",
        "trend": "1m bullish, 5m bullish, above 1h EMA100",
        "change_24h": +2.5,
        "change_1h": +0.8,
        "sentiment": "Fear & Greed: 72/100 (GREED)",
        "current_position": "None"
    }

    strategy = AITradingStrategy(bot_config, model_config, api_key)
    decision = strategy.get_trading_decision(market_data)

    print("=" * 60)
    print("AI Trading Decision")
    print("=" * 60)
    print(f"Decision: {decision['decision']}")
    print(f"Confidence: {decision['confidence']}%")
    print(f"Reasoning: {decision['reasoning']}")
    print(f"Cost: ${decision['api_cost']:.6f}")
    print("=" * 60)
