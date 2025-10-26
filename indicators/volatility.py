import pandas as pd
import numpy as np
from typing import Tuple, Optional


class VolatilityIndicators:
    """
    Calculate various volatility indicators for cryptocurrency trading.
    """

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
        """
        Calculate Average True Range (ATR).

        ATR measures market volatility by decomposing the entire range of an asset price
        for that period. Higher ATR values indicate higher volatility.

        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            period: Number of periods for ATR calculation (default: 14)

        Returns:
            Latest ATR value, or None if insufficient data
        """
        if df.empty or len(df) < period:
            return None

        # Calculate True Range
        df = df.copy()
        df['h-l'] = df['high'] - df['low']
        df['h-pc'] = abs(df['high'] - df['close'].shift(1))
        df['l-pc'] = abs(df['low'] - df['close'].shift(1))

        df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)

        # Calculate ATR using EMA
        atr = df['tr'].ewm(span=period, adjust=False).mean()

        return float(atr.iloc[-1]) if not atr.empty else None

    @staticmethod
    def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20,
                                  std_dev: float = 2.0) -> Optional[Tuple[float, float, float]]:
        """
        Calculate Bollinger Bands.

        Bollinger Bands consist of a middle band (SMA) and two outer bands (standard deviations).
        The width of the bands indicates volatility - wider bands mean higher volatility.

        Args:
            df: DataFrame with 'close' column
            period: Number of periods for moving average (default: 20)
            std_dev: Number of standard deviations for bands (default: 2.0)

        Returns:
            Tuple of (upper_band, middle_band, lower_band), or None if insufficient data
        """
        if df.empty or len(df) < period:
            return None

        # Calculate middle band (SMA)
        sma = df['close'].rolling(window=period).mean()

        # Calculate standard deviation
        std = df['close'].rolling(window=period).std()

        # Calculate upper and lower bands
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)

        if sma.iloc[-1] is None or pd.isna(sma.iloc[-1]):
            return None

        return (
            float(upper_band.iloc[-1]),
            float(sma.iloc[-1]),
            float(lower_band.iloc[-1])
        )

    @staticmethod
    def calculate_bollinger_band_width(df: pd.DataFrame, period: int = 20,
                                       std_dev: float = 2.0) -> Optional[float]:
        """
        Calculate Bollinger Band Width as a percentage.

        Bollinger Band Width = ((Upper Band - Lower Band) / Middle Band) * 100

        This is a direct measure of volatility. Higher values indicate higher volatility.

        Args:
            df: DataFrame with 'close' column
            period: Number of periods for moving average (default: 20)
            std_dev: Number of standard deviations for bands (default: 2.0)

        Returns:
            Bollinger Band Width percentage, or None if insufficient data
        """
        bands = VolatilityIndicators.calculate_bollinger_bands(df, period, std_dev)

        if bands is None:
            return None

        upper, middle, lower = bands

        if middle == 0:
            return None

        bb_width = ((upper - lower) / middle) * 100

        return float(bb_width)

    @staticmethod
    def calculate_historical_volatility(df: pd.DataFrame, period: int = 20) -> Optional[float]:
        """
        Calculate Historical Volatility (standard deviation of returns).

        This measures the dispersion of returns for a given security over a given period.

        Args:
            df: DataFrame with 'close' column
            period: Number of periods for calculation (default: 20)

        Returns:
            Historical volatility as a percentage, or None if insufficient data
        """
        if df.empty or len(df) < period + 1:
            return None

        # Calculate log returns
        df = df.copy()
        df['returns'] = np.log(df['close'] / df['close'].shift(1))

        # Calculate standard deviation of returns
        volatility = df['returns'].rolling(window=period).std()

        if volatility.iloc[-1] is None or pd.isna(volatility.iloc[-1]):
            return None

        # Annualize and convert to percentage
        # For crypto (24/7 trading), we use sqrt(365*24) for hourly data, or adjust accordingly
        # For simplicity, we'll return daily volatility as percentage
        return float(volatility.iloc[-1] * 100)

    @staticmethod
    def calculate_price_change_percentage(df: pd.DataFrame, periods: int = 24) -> Optional[float]:
        """
        Calculate percentage price change over specified periods.

        Args:
            df: DataFrame with 'close' column
            periods: Number of periods to look back (default: 24)

        Returns:
            Price change percentage, or None if insufficient data
        """
        if df.empty or len(df) < periods + 1:
            return None

        current_price = df['close'].iloc[-1]
        past_price = df['close'].iloc[-(periods + 1)]

        if past_price == 0:
            return None

        price_change_pct = ((current_price - past_price) / past_price) * 100

        return float(price_change_pct)

    @staticmethod
    def calculate_decline_velocity(df: pd.DataFrame) -> Optional[dict]:
        """
        Calculate decline velocity metrics to distinguish between healthy pullbacks and crashes.

        A slow, controlled decline is GOOD for Martingale (safe to average down).
        A fast crash is DANGEROUS (risk of getting stuck in bad position).

        Args:
            df: DataFrame with OHLC and volume data

        Returns:
            Dict with decline velocity metrics, or None if insufficient data
        """
        if df.empty or len(df) < 30:
            return None

        metrics = {}

        # 1. Short-term rate of change (last 5 periods) - detects crashes
        if len(df) >= 6:
            short_term_roc = ((df['close'].iloc[-1] - df['close'].iloc[-6]) / df['close'].iloc[-6]) * 100
            metrics['roc_5'] = float(short_term_roc)

        # 2. Medium-term rate of change (last 15 periods) - detects trend
        if len(df) >= 16:
            medium_term_roc = ((df['close'].iloc[-1] - df['close'].iloc[-16]) / df['close'].iloc[-16]) * 100
            metrics['roc_15'] = float(medium_term_roc)

        # 3. Long-term rate of change (last 30 periods) - detects overall direction
        if len(df) >= 31:
            long_term_roc = ((df['close'].iloc[-1] - df['close'].iloc[-31]) / df['close'].iloc[-31]) * 100
            metrics['roc_30'] = float(long_term_roc)

        # 4. Decline smoothness - compare short vs medium term
        # If short-term drop is much worse than medium-term = crash
        # If they're similar = smooth controlled decline
        if 'roc_5' in metrics and 'roc_15' in metrics:
            if metrics['roc_15'] != 0:
                smoothness_ratio = abs(metrics['roc_5'] / metrics['roc_15'])
                metrics['smoothness_ratio'] = float(smoothness_ratio)
                # Ratio > 2.0 means short-term drop is 2x worse = jerky/crash
                # Ratio ~1.0 means steady decline = smooth
            else:
                metrics['smoothness_ratio'] = 1.0

        # 5. Volume spike detection (if volume data available)
        if 'volume' in df.columns and len(df) >= 21:
            recent_volume = df['volume'].iloc[-5:].mean()
            avg_volume = df['volume'].iloc[-21:-5].mean()

            if avg_volume > 0:
                volume_ratio = recent_volume / avg_volume
                metrics['volume_ratio'] = float(volume_ratio)
                # Ratio > 2.0 = volume spike (potential panic selling)

        # 6. Calculate decline velocity score (0-100)
        # Lower score = safer to add to position
        # Higher score = dangerous, avoid adding
        velocity_score = 0

        # Check short-term ROC (most important)
        if 'roc_5' in metrics:
            if metrics['roc_5'] < -5:  # Dropped >5% in 5 periods
                velocity_score += 40
            elif metrics['roc_5'] < -3:  # Dropped 3-5%
                velocity_score += 25
            elif metrics['roc_5'] < -1:  # Dropped 1-3% (healthy pullback)
                velocity_score += 10

        # Check smoothness
        if 'smoothness_ratio' in metrics:
            if metrics['smoothness_ratio'] > 2.5:  # Very jerky
                velocity_score += 30
            elif metrics['smoothness_ratio'] > 1.5:  # Somewhat jerky
                velocity_score += 15

        # Check volume spike
        if 'volume_ratio' in metrics:
            if metrics['volume_ratio'] > 3.0:  # Major volume spike
                velocity_score += 30
            elif metrics['volume_ratio'] > 2.0:  # Moderate spike
                velocity_score += 15

        metrics['velocity_score'] = min(100, velocity_score)

        # Determine decline type
        if velocity_score >= 70:
            metrics['decline_type'] = 'CRASH'  # Dangerous - avoid adding
        elif velocity_score >= 40:
            metrics['decline_type'] = 'FAST_DECLINE'  # Risky - be cautious
        elif velocity_score >= 20:
            metrics['decline_type'] = 'MODERATE_DECLINE'  # Acceptable
        else:
            metrics['decline_type'] = 'SLOW_DECLINE'  # Good for averaging down

        return metrics

    @staticmethod
    def is_high_volatility(df: pd.DataFrame, atr_threshold: float = None,
                          bb_width_threshold: float = 8.0,
                          hist_vol_threshold: float = 5.0) -> Tuple[bool, dict]:
        """
        Determine if current market conditions indicate high volatility.

        Args:
            df: DataFrame with OHLC data
            atr_threshold: ATR threshold (if None, uses 1.5x the 50-period ATR average)
            bb_width_threshold: Bollinger Band width threshold percentage (default: 8.0%)
            hist_vol_threshold: Historical volatility threshold percentage (default: 5.0%)

        Returns:
            Tuple of (is_high_volatility: bool, metrics: dict)
        """
        metrics = {}

        # Calculate ATR
        atr = VolatilityIndicators.calculate_atr(df)
        if atr:
            metrics['atr'] = atr

            # If no threshold provided, calculate dynamic threshold
            if atr_threshold is None and len(df) >= 50:
                atr_series = []
                for i in range(14, min(51, len(df) + 1)):
                    atr_val = VolatilityIndicators.calculate_atr(df.iloc[:i])
                    if atr_val:
                        atr_series.append(atr_val)

                if atr_series:
                    atr_threshold = np.mean(atr_series) * 1.5
                    metrics['atr_threshold'] = atr_threshold

        # Calculate Bollinger Band Width
        bb_width = VolatilityIndicators.calculate_bollinger_band_width(df)
        if bb_width:
            metrics['bb_width'] = bb_width

        # Calculate Historical Volatility
        hist_vol = VolatilityIndicators.calculate_historical_volatility(df)
        if hist_vol:
            metrics['historical_volatility'] = hist_vol

        # Determine if high volatility
        is_high_vol = False

        if atr_threshold and atr and atr > atr_threshold:
            is_high_vol = True
            metrics['trigger'] = 'atr'

        elif bb_width and bb_width > bb_width_threshold:
            is_high_vol = True
            metrics['trigger'] = 'bb_width'

        elif hist_vol and hist_vol > hist_vol_threshold:
            is_high_vol = True
            metrics['trigger'] = 'historical_volatility'

        return is_high_vol, metrics
