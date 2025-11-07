"""
AI Trading Strategy
Uses LLM models via OpenRouter.ai to make trading decisions
based on comprehensive market analysis.

OpenRouter provides unified access to 400+ AI models including:
GPT-4o, Claude Sonnet 4.5, Gemini 2.5 Flash, DeepSeek V3.1, and more
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
    AI-powered trading strategy using LLM for decision-making via OpenRouter

    OpenRouter provides unified access to all major AI models:
    - OpenAI: GPT-4o, GPT-4o-mini, GPT-5 Pro
    - Anthropic: Claude Sonnet 4.5, Claude Opus 4.5
    - Google: Gemini 2.5 Flash, Gemini 2.5 Pro
    - DeepSeek: DeepSeek V3.1 Terminus
    - Meta: Llama 3.3 70B, Llama 4.1 405B
    - And 400+ more models
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

        # Get virtual balance info
        virtual_balance = self.bot_config.get('virtual_balance', 100.00)

        # Symbol constraints (if available)
        symbol_constraints = market_data.get('symbol_constraints', {})
        constraints_text = ""
        if symbol_constraints:
            min_qty = symbol_constraints.get('min_order_qty', 'N/A')
            max_qty = symbol_constraints.get('max_order_qty', 'N/A')
            step = symbol_constraints.get('qty_step', 'N/A')
            current_price = market_data.get('current_price', 1)

            # Calculate minimum USD value
            min_value_usd = float(min_qty) * float(current_price) if min_qty != 'N/A' else 0

            constraints_text = f"""
**EXCHANGE CONSTRAINTS FOR {self.bot_config['symbol']}:**
- Minimum Order Quantity: {min_qty} contracts (≈ ${min_value_usd:.2f} at current price)
- Maximum Order Quantity: {max_qty} contracts
- Quantity Step Size: {step} contracts (must be multiples of this)
- Your position size must account for these constraints"""

        # Trading rules section
        rules_section = f"""
**YOUR TRADING ACCOUNT:**
- Virtual Balance: ${virtual_balance:.2f}
- Max Position Size: {self.bot_config['max_position_size'] * 100}% of balance (you decide actual %)
- Max Leverage: {self.bot_config['leverage']}x (you decide actual leverage)
- Position Style: {self.bot_config['side']} preferred (but you can choose Long/Short)
- Risk Profile: {self.bot_config.get('risk_profile', 'moderate')}
{constraints_text}

**TRADING RULES:**
- You MUST decide position size (1-{self.bot_config['max_position_size'] * 100}% of balance)
- You MUST decide leverage (1-{self.bot_config['leverage']}x)
- You MUST set stop-loss and take-profit levels
- Risk management is critical - be conservative
- IMPORTANT: Ensure your position size meets the minimum order requirement shown above"""

        # Build full prompt
        prompt = f"""You are an expert cryptocurrency trading AI assistant with FULL AUTONOMY over trade execution. Analyze ALL available data sources and make a complete trading decision.

{technical_section}

{sentiment_section}

{position_section}

{rules_section}

**YOUR TASK:**
Based on the comprehensive analysis above, make a COMPLETE trading decision:

1. **Direction:** BUY, SELL, or HOLD?
2. **Position Size:** What % of your ${virtual_balance:.2f} balance to use? (Max: {self.bot_config['max_position_size'] * 100}%)
3. **Leverage:** What leverage multiplier? (Max: {self.bot_config['leverage']}x)
4. **Risk Management:** Set stop-loss and take-profit levels

**IMPORTANT:**
- Larger positions = higher risk, require higher confidence
- Use leverage proportional to confidence: 70-80% confidence → 3-5x leverage, 80-90% → 5-8x leverage
- Consider market volatility when sizing positions
- Keep reasoning concise but insightful (3-4 sentences)
- Be conservative with confidence scores but reasonable with leverage (avoid 1x unless low confidence)

**Output Format (JSON only, no markdown):**
{{
  "decision": "BUY|SELL|HOLD",
  "position_size_pct": 0.03,
  "leverage": 3,
  "confidence": 75,
  "reasoning": "Brief 3-4 sentence explanation covering technical signals, sentiment, position sizing rationale, and key risks",
  "risk_level": "LOW|MEDIUM|HIGH",
  "stop_loss": {price * 0.98:.2f},
  "take_profit": {price * 1.03:.2f}
}}

**Example valid responses:**
- Conservative: {{"decision": "BUY", "position_size_pct": 0.02, "leverage": 2, "confidence": 65, ...}}
- Moderate: {{"decision": "SELL", "position_size_pct": 0.05, "leverage": 5, "confidence": 80, ...}}
- Aggressive: {{"decision": "BUY", "position_size_pct": {self.bot_config['max_position_size']}, "leverage": {self.bot_config['leverage']}, "confidence": 90, ...}}

Respond with ONLY the JSON, no other text."""

        return prompt

    def _call_ai_api(self, prompt: str) -> Dict:
        """
        Call the AI model API via OpenRouter

        OpenRouter provides unified access to all AI models with OpenAI-compatible API
        """
        # OpenRouter requires specific headers
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://dcabot.com",  # Required by OpenRouter
            "X-Title": "DCABot Trading Platform"    # Optional but recommended
        }

        # Detect if this is a portfolio decision (needs more tokens)
        is_portfolio = 'PORTFOLIO:' in prompt or 'portfolio_action' in prompt
        max_tokens = 6000 if is_portfolio else 4000

        # OpenAI-compatible payload (supported by all models via OpenRouter)
        payload = {
            "model": self.model_identifier,  # e.g., "anthropic/claude-3.5-sonnet", "openai/gpt-4o-mini"
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
            "max_tokens": max_tokens
        }

        # Make API call
        # Log API call details for debugging
        logger.info(f"[API DEBUG] Prompt length: {len(prompt)} characters")
        logger.info(f"[API DEBUG] Calling OpenRouter API: {self.api_endpoint}")
        logger.info(f"[API DEBUG] Model: {self.model_identifier} ({self.model_config['name']})")

        # Use longer timeout for portfolio decisions (check if prompt contains portfolio keywords)
        # Standard single-symbol: 90s, Portfolio multi-symbol: 180s (3 minutes)
        is_portfolio = 'PORTFOLIO:' in prompt or 'portfolio_action' in prompt
        timeout = 180 if is_portfolio else 90
        logger.info(f"[API DEBUG] Type: {'Portfolio' if is_portfolio else 'Single'} | Timeout: {timeout}s")

        try:
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            response_json = response.json()

            # Log response details (OpenRouter returns OpenAI-compatible format)
            logger.info(f"[API DEBUG] Response status: {response.status_code}")
            choices = response_json.get('choices', [])
            if choices:
                finish_reason = choices[0].get('finish_reason', 'N/A')
                content = choices[0].get('message', {}).get('content', '')
                usage = response_json.get('usage', {})
                logger.info(f"[API DEBUG] Finish reason: {finish_reason}")
                logger.info(f"[API DEBUG] Content length: {len(content)} characters")
                logger.info(f"[API DEBUG] Usage: {usage}")
                logger.info(f"[API DEBUG] Content preview (first 200 chars): {content[:200]}")
                if finish_reason == 'length' and len(content) < 100:
                    logger.error(f"[API DEBUG] ISSUE: finish_reason='length' but content is very short!")
                    logger.error(f"[API DEBUG] Full response: {response_json}")
            else:
                logger.warning(f"[API DEBUG] No choices in response!")
                logger.info(f"[API DEBUG] Full response: {response_json}")

            return response_json

        except requests.exceptions.Timeout:
            raise Exception(f"API timeout after {timeout}s ({self.model_config['name']})")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"API error {response.status_code}: {response.text}")
        except Exception as e:
            raise Exception(f"Unexpected API error: {e}")

    def _parse_ai_response(self, response: Dict) -> Dict[str, Any]:
        """
        Parse AI response and extract decision

        OpenRouter returns OpenAI-compatible format for all models
        """
        try:
            # Extract content from OpenAI-compatible response format
            message = response['choices'][0]['message']
            content = message.get('content', '')

            if not content or content.strip() == '':
                logger.error("Response content is empty")
                raise ValueError("Empty response content from AI model")

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
            required_fields = ['decision', 'position_size_pct', 'leverage', 'confidence', 'reasoning', 'risk_level', 'stop_loss', 'take_profit']
            for field in required_fields:
                if field not in decision:
                    raise ValueError(f"Missing required field: {field}")

            # Validate decision value
            if decision['decision'] not in ['BUY', 'SELL', 'HOLD']:
                raise ValueError(f"Invalid decision: {decision['decision']}")

            # Validate position_size_pct (0.01 to max_position_size)
            max_pos_size = float(self.bot_config.get('max_position_size', 0.10))
            if not (0.01 <= decision['position_size_pct'] <= max_pos_size):
                logger.warning(f"Position size {decision['position_size_pct']} out of range, clamping to 0.01-{max_pos_size}")
                decision['position_size_pct'] = max(0.01, min(max_pos_size, decision['position_size_pct']))

            # Validate leverage (1 to max_leverage)
            max_lev = int(self.bot_config.get('leverage', 10))
            if not (1 <= decision['leverage'] <= max_lev):
                logger.warning(f"Leverage {decision['leverage']} out of range, clamping to 1-{max_lev}")
                decision['leverage'] = max(1, min(max_lev, int(decision['leverage'])))

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

    def get_portfolio_decision(self, portfolio_context: Dict) -> Dict[str, Any]:
        """
        Make portfolio-level decision for multiple symbols at once

        Args:
            portfolio_context: Dict with balance, positions, market_data, symbol_constraints

        Returns:
            Dict with portfolio_action, decisions (per symbol), reasoning, etc.
        """
        try:
            # Build portfolio prompt
            prompt = self.build_portfolio_prompt(portfolio_context)

            # Call AI API
            start_time = time.time()
            response = self._call_ai_api(prompt)
            response_time_ms = int((time.time() - start_time) * 1000)

            # Parse response
            decision = self._parse_portfolio_response(response)
            decision['response_time_ms'] = response_time_ms

            return decision

        except Exception as e:
            logger.error(f"Error getting portfolio decision: {e}", exc_info=True)
            return {
                'portfolio_action': 'ERROR',
                'decisions': {},
                'reasoning': f'Error: {str(e)}',
                'api_cost': 0,
                'response_time_ms': 0
            }

    def build_portfolio_prompt(self, portfolio_context: Dict) -> str:
        """Build compressed prompt for portfolio-level decision"""
        balance = portfolio_context['balance']
        positions = portfolio_context['positions']
        market_data = portfolio_context['market_data']
        symbol_constraints = portfolio_context['symbol_constraints']
        symbols = portfolio_context['symbols']

        # Build market analysis for all symbols (moderately compressed)
        market_analysis = []
        for symbol in symbols:
            md = market_data[symbol]
            constraints = symbol_constraints[symbol]
            position = positions.get(symbol)

            min_qty = constraints['min_order_qty']
            current_price = md['current_price']
            min_value_usd = float(min_qty) * float(current_price) if min_qty else 0

            # Balanced format: readable but not verbose
            symbol_section = f"""**{symbol}:**
Price: ${md['current_price']:.0f} | 24h: {md.get('change_24h', 0):+.1f}% | RSI: {md.get('rsi', 50)}
EMAs: 20m={md.get('ema20_1m', 0):.0f} 50m={md.get('ema50_5m', 0):.0f} 100h={md.get('ema100_1h', 0):.0f}
Vol: {md.get('volume_trend', 'N/A')} | MinOrder: {min_qty} (${min_value_usd:.0f})
Position: {position if position else 'None'}"""

            market_analysis.append(symbol_section)

        market_section = "\n".join(market_analysis)

        # Portfolio overview
        deployed_pct = (balance['used'] / balance['total'] * 100) if balance['total'] > 0 else 0
        portfolio_section = f"""**PORTFOLIO:**
Total: ${balance['total']:.0f} | Available: ${balance['available']:.0f} | Used: ${balance['used']:.0f}
Deployed: {deployed_pct:.1f}% | Symbols: {', '.join(symbols)}"""

        # Build prompt with clear structure
        prompt = f"""You are an expert cryptocurrency portfolio manager managing {len(symbols)} trading pairs.

{portfolio_section}

**MARKET DATA:**
{market_section}

**TASK:**
Analyze the portfolio and provide a decision for each symbol.

1. **Portfolio Action:** Choose one: HOLD_ALL, REBALANCE, EXPAND, LIQUIDATE, HEDGE
2. **Per-Symbol Decisions:** For each symbol provide decision, confidence, position_size_pct, leverage, stop_loss, take_profit, reasoning, risk_level
3. **Risk Assessment:** Overall portfolio risk

**RULES:**
- Consider correlations (BTC/ETH move together)
- Balance diversification
- Can HOLD some symbols while BUY/SELL others
- Available to spend: ${balance['available']:.0f}
- Meet minimum order sizes
- Use leverage proportional to confidence: 70-80% confidence → 3-5x leverage, 80-90% → 5-8x leverage
- Avoid 1x leverage unless confidence is low (<70%)

**OUTPUT (JSON only, no markdown):**
{{
  "portfolio_action": "REBALANCE|HOLD_ALL|EXPAND|LIQUIDATE|HEDGE",
  "risk_assessment": "Brief risk assessment",
  "reasoning": "Why this portfolio action",
  "decisions": {{
    "BTCUSDT": {{"decision": "BUY|SELL|HOLD|REDUCE|CLOSE", "confidence": 75, "position_size_pct": 0.03, "leverage": 3, "stop_loss": 67500, "take_profit": 70000, "reasoning": "Why", "risk_level": "MEDIUM"}},
    "ETHUSDT": {{...}},
    ... for each symbol
  }}
}}"""


        return prompt

    def _parse_portfolio_response(self, response: Dict) -> Dict[str, Any]:
        """Parse AI response for portfolio decision (via OpenRouter)"""
        try:
            # Extract content from OpenAI-compatible response format
            message = response['choices'][0]['message']
            content = message.get('content', '')
            usage = response.get('usage', {})

            # Log raw response for debugging
            logger.info(f"Raw AI response (first 500 chars): {content[:500]}")

            # Try to parse JSON
            try:
                # Extract JSON from markdown code blocks
                if '```json' in content:
                    json_str = content.split('```json')[1].split('```')[0].strip()
                elif '```' in content:
                    json_str = content.split('```')[1].split('```')[0].strip()
                else:
                    # Try to find JSON object in content
                    start = content.find('{')
                    if start != -1:
                        # Find matching closing brace
                        brace_count = 0
                        for i in range(start, len(content)):
                            if content[i] == '{':
                                brace_count += 1
                            elif content[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    json_str = content[start:i+1]
                                    break
                        else:
                            json_str = content[start:].strip()
                    else:
                        json_str = content.strip()

                logger.info(f"Extracted JSON (first 300 chars): {json_str[:300]}")
                decision = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                logger.error(f"Failed JSON string: {json_str[:500]}")
                # Try to fix truncated JSON
                decision = self._fix_truncated_json(json_str if 'json_str' in locals() else content)

            # Validate and fix missing leverage/position_size values in portfolio decisions
            if 'decisions' in decision and isinstance(decision['decisions'], dict):
                for symbol, decision_data in decision['decisions'].items():
                    # Ensure leverage is always present and valid
                    max_lev = int(self.bot_config.get('leverage', 10))
                    if 'leverage' not in decision_data or decision_data['leverage'] is None:
                        default_leverage = min(max_lev, 5)  # Default to 5x or max allowed (more reasonable)
                        decision_data['leverage'] = default_leverage
                        logger.warning(f"Portfolio decision for {symbol} missing leverage, setting to {default_leverage}x")
                    else:
                        # Ensure leverage is integer and within bounds
                        try:
                            leverage_value = int(decision_data['leverage'])
                            # If AI chose 1x, boost it to at least 3x unless max leverage is very low
                            if leverage_value == 1 and max_lev >= 3:
                                leverage_value = 3
                                logger.info(f"AI chose 1x leverage for {symbol}, boosting to 3x for better risk-adjusted returns")
                            decision_data['leverage'] = max(1, min(max_lev, leverage_value))
                        except (ValueError, TypeError):
                            default_leverage = min(max_lev, 5)
                            decision_data['leverage'] = default_leverage
                            logger.warning(f"Portfolio decision for {symbol} has invalid leverage, setting to {default_leverage}x")

                    # Ensure position_size_pct is always present and valid
                    max_pos = float(self.bot_config.get('max_position_size', 0.10))
                    if 'position_size_pct' not in decision_data or decision_data['position_size_pct'] is None:
                        default_pos_size = 0.02  # Default to 2%
                        decision_data['position_size_pct'] = default_pos_size
                        logger.warning(f"Portfolio decision for {symbol} missing position_size_pct, setting to {default_pos_size*100:.1f}%")
                    else:
                        try:
                            decision_data['position_size_pct'] = max(0.01, min(max_pos, float(decision_data['position_size_pct'])))
                        except (ValueError, TypeError):
                            decision_data['position_size_pct'] = 0.02
                            logger.warning(f"Portfolio decision for {symbol} has invalid position_size_pct, setting to 2.0%")

            # Calculate cost
            input_tokens = usage.get('prompt_tokens', 0)
            output_tokens = usage.get('completion_tokens', 0)
            api_cost = self._calculate_cost(input_tokens, output_tokens)

            # Add metadata
            decision['input_tokens'] = input_tokens
            decision['output_tokens'] = output_tokens
            decision['api_cost'] = api_cost

            return decision

        except Exception as e:
            logger.error(f"Error parsing portfolio response: {e}")
            return {
                'portfolio_action': 'ERROR',
                'decisions': {},
                'reasoning': f'Parse error: {str(e)}',
                'api_cost': 0
            }


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
