"""
Market Data Fetcher for AI Trading Bots
Fetches comprehensive market data from multiple sources:
- Technical indicators (Binance)
- Sentiment data (Fear & Greed Index)
- News headlines (optional)
"""

import requests
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Fetch multi-source market data for AI analysis"""

    def __init__(self, binance_api_url: str = "https://api.binance.com/api/v3"):
        self.binance_api_url = binance_api_url

    def fetch_all_data(self, symbol: str, current_position: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Fetch comprehensive market data for AI decision-making

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            current_position: Current position info if exists

        Returns:
            Dict with technical, sentiment, and contextual data
        """
        try:
            # Fetch technical data
            technical_data = self.fetch_technical_data(symbol)

            # Fetch sentiment data
            sentiment_data = self.fetch_sentiment_data(symbol)

            # Combine all data
            market_data = {
                **technical_data,
                **sentiment_data,
                "current_position": self._format_position(current_position) if current_position else "None",
                "fetched_at": datetime.now().isoformat()
            }

            return market_data

        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            raise

    def fetch_technical_data(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch technical indicators from Binance

        Returns:
            Dict with price, EMAs, RSI, volume trends
        """
        logger.info(f"Fetching technical data for {symbol}...")

        try:
            # Get current price and 24h stats
            ticker_url = f"{self.binance_api_url}/ticker/24hr?symbol={symbol}"
            ticker_response = requests.get(ticker_url, timeout=10)
            ticker_response.raise_for_status()
            ticker_data = ticker_response.json()

            current_price = float(ticker_data['lastPrice'])
            price_change_24h = float(ticker_data['priceChangePercent'])

            # Calculate EMAs
            ema20_1m = self._get_ema(symbol, '1m', 20)
            ema50_5m = self._get_ema(symbol, '5m', 50)
            ema100_1h = self._get_ema(symbol, '1h', 100)

            # Calculate RSI
            rsi = self._calculate_rsi(symbol, '1m', 14)

            # Analyze volume trend
            volume_trend = self._analyze_volume_trend(symbol)

            # Determine trend description
            trend_description = self._describe_trend(
                current_price, ema20_1m, ema50_5m, ema100_1h
            )

            # Calculate 1h change
            klines_1h = requests.get(
                f"{self.binance_api_url}/klines?symbol={symbol}&interval=1h&limit=2",
                timeout=10
            ).json()
            price_1h_ago = float(klines_1h[-2][4])
            change_1h = ((current_price - price_1h_ago) / price_1h_ago) * 100

            return {
                "symbol": symbol,
                "current_price": current_price,
                "ema20_1m": ema20_1m,
                "ema50_5m": ema50_5m,
                "ema100_1h": ema100_1h,
                "rsi": round(rsi, 1),
                "volume_trend": volume_trend,
                "trend": trend_description,
                "change_24h": round(price_change_24h, 2),
                "change_1h": round(change_1h, 2)
            }

        except Exception as e:
            logger.error(f"Error fetching technical data: {e}")
            raise

    def _get_ema(self, symbol: str, interval: str, period: int) -> float:
        """Calculate EMA for given interval and period"""
        try:
            klines_url = f"{self.binance_api_url}/klines?symbol={symbol}&interval={interval}&limit={period + 50}"
            klines_response = requests.get(klines_url, timeout=10)
            klines_response.raise_for_status()
            klines = klines_response.json()

            closes = [float(k[4]) for k in klines]  # Close prices
            df = pd.DataFrame({'close': closes})
            ema = df['close'].ewm(span=period, adjust=False).mean().iloc[-1]

            return float(ema)

        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            raise

    def _calculate_rsi(self, symbol: str, interval: str = '1m', period: int = 14) -> float:
        """Calculate RSI indicator"""
        try:
            klines_url = f"{self.binance_api_url}/klines?symbol={symbol}&interval={interval}&limit={period + 50}"
            klines_response = requests.get(klines_url, timeout=10)
            klines_response.raise_for_status()
            klines = klines_response.json()

            closes = [float(k[4]) for k in klines]
            df = pd.DataFrame({'close': closes})

            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            return float(rsi.iloc[-1])

        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            raise

    def _analyze_volume_trend(self, symbol: str) -> str:
        """Analyze volume trend (increasing, decreasing, stable)"""
        try:
            klines_5m = requests.get(
                f"{self.binance_api_url}/klines?symbol={symbol}&interval=5m&limit=20",
                timeout=10
            ).json()

            recent_volumes = [float(k[5]) for k in klines_5m[-5:]]
            older_volumes = [float(k[5]) for k in klines_5m[-10:-5]]

            avg_recent = sum(recent_volumes) / len(recent_volumes)
            avg_older = sum(older_volumes) / len(older_volumes)

            if avg_recent > avg_older * 1.1:
                return "INCREASING"
            elif avg_recent < avg_older * 0.9:
                return "DECREASING"
            else:
                return "STABLE"

        except Exception as e:
            logger.error(f"Error analyzing volume: {e}")
            return "UNKNOWN"

    def _describe_trend(self, price: float, ema20: float, ema50: float, ema100: float) -> str:
        """Generate human-readable trend description"""
        parts = []

        # 1min vs 5min
        if ema20 > ema50:
            parts.append("1m bullish")
        else:
            parts.append("1m bearish")

        # 5min vs 1h
        if ema50 > ema100:
            parts.append("5m bullish")
        else:
            parts.append("5m bearish")

        # Price vs 1h EMA
        if price > ema100:
            parts.append("above 1h EMA100")
        else:
            parts.append("below 1h EMA100")

        return ", ".join(parts)

    def fetch_sentiment_data(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch sentiment indicators

        Currently fetches:
        - Fear & Greed Index (crypto-wide)
        - Future: Twitter sentiment, Reddit sentiment

        Returns:
            Dict with sentiment data
        """
        try:
            # Fetch Fear & Greed Index
            fear_greed = self._get_fear_greed_index()

            # TODO: Add Twitter/social sentiment
            # TODO: Add Reddit sentiment
            # TODO: Add Google Trends data

            sentiment_description = self._format_sentiment_description(fear_greed)

            return {
                "fear_greed_index": fear_greed,
                "sentiment": sentiment_description
            }

        except Exception as e:
            logger.warning(f"Error fetching sentiment data: {e}")
            # Return neutral sentiment on error
            return {
                "fear_greed_index": None,
                "sentiment": "Sentiment data unavailable"
            }

    def _get_fear_greed_index(self) -> Optional[int]:
        """
        Fetch Fear & Greed Index from alternative.me API

        Returns:
            Integer 0-100, or None if unavailable
        """
        try:
            response = requests.get(
                "https://api.alternative.me/fng/",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            value = int(data['data'][0]['value'])
            return value

        except Exception as e:
            logger.warning(f"Error fetching Fear & Greed Index: {e}")
            return None

    def _format_sentiment_description(self, fear_greed: Optional[int]) -> str:
        """Format sentiment into human-readable description"""
        if fear_greed is None:
            return "Sentiment: N/A"

        if fear_greed <= 20:
            label = "EXTREME FEAR"
        elif fear_greed <= 40:
            label = "FEAR"
        elif fear_greed <= 60:
            label = "NEUTRAL"
        elif fear_greed <= 80:
            label = "GREED"
        else:
            label = "EXTREME GREED"

        return f"Fear & Greed: {fear_greed}/100 ({label})"

    def _format_position(self, position: Dict) -> str:
        """Format current position info for prompt"""
        if not position or position.get('size', 0) == 0:
            return "None"

        side = position.get('side', 'Unknown')
        size = position.get('size', 0)
        entry_price = position.get('entry_price', 0)
        current_price = position.get('current_price', 0)

        if entry_price > 0 and current_price > 0:
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            pnl_sign = "+" if pnl_pct >= 0 else ""

            return f"{side} {size} @ ${entry_price:,.2f} (PnL: {pnl_sign}{pnl_pct:.2f}%)"
        else:
            return f"{side} {size} @ ${entry_price:,.2f}"

    def fetch_news_headlines(self, symbol: str, limit: int = 5) -> list:
        """
        Fetch recent news headlines for the symbol

        TODO: Integrate with:
        - CoinDesk API
        - CoinTelegraph RSS
        - CryptoPanic API
        - NewsAPI

        Returns:
            List of headline strings
        """
        # Placeholder for future implementation
        logger.info("News fetching not yet implemented")
        return []


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    fetcher = MarketDataFetcher()
    data = fetcher.fetch_all_data("BTCUSDT")

    print("=" * 60)
    print("Market Data for BTCUSDT")
    print("=" * 60)
    print(f"Price: ${data['current_price']:,.2f}")
    print(f"RSI: {data['rsi']}")
    print(f"Trend: {data['trend']}")
    print(f"Sentiment: {data['sentiment']}")
    print("=" * 60)
