import math
from typing import List, Dict, Any, Optional

class TechnicalAnalyzer:
    """
    Высокопроизводительный аналитический модуль для расчета технических индикаторов
    и анализа микроструктуры стакана (Orderbook Imbalance).
    """

    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        """Расчет экспоненциальной скользящей средней (EMA)."""
        if len(prices) < period:
            return []
        k = 2.0 / (period + 1.0)
        # Начальное значение - SMA
        ema = [sum(prices[:period]) / period]
        for price in prices[period:]:
            ema.append(price * k + ema[-1] * (1.0 - k))
        return ema

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """Расчет индекса относительной силы (RSI)."""
        if len(prices) <= period:
            return 50.0

        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change >= 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))

        # Первоначальное среднее
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        # Сглаживание по Уайлдеру
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0.0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return round(rsi, 2)

    @staticmethod
    def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """Расчет MACD (Moving Average Convergence Divergence)."""
        if len(prices) < slow + signal:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

        ema_fast = TechnicalAnalyzer.calculate_ema(prices, fast)
        ema_slow = TechnicalAnalyzer.calculate_ema(prices, slow)

        # Выравнивание длины: разница между быстрой и медленной EMA
        offset = slow - fast
        macd_line = [fast_v - slow_v for fast_v, slow_v in zip(ema_fast[offset:], ema_slow)]

        if len(macd_line) < signal:
            return {"macd": round(macd_line[-1], 4), "signal": 0.0, "histogram": 0.0}

        signal_line = TechnicalAnalyzer.calculate_ema(macd_line, signal)
        current_macd = macd_line[-1]
        current_signal = signal_line[-1] if signal_line else 0.0
        histogram = current_macd - current_signal

        return {
            "macd": round(current_macd, 4),
            "signal": round(current_signal, 4),
            "histogram": round(histogram, 4),
        }

    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev_mult: float = 2.0) -> Dict[str, float]:
        """Расчет полос Боллинджера (Bollinger Bands)."""
        if len(prices) < period:
            current_p = prices[-1] if prices else 0.0
            return {"upper": current_p, "middle": current_p, "lower": current_p, "bandwidth_pct": 0.0, "percent_b": 0.5}

        window = prices[-period:]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        std_dev = math.sqrt(variance)

        upper = sma + (std_dev * std_dev_mult)
        lower = sma - (std_dev * std_dev_mult)
        current_price = prices[-1]

        bandwidth = (upper - lower) / sma * 100.0 if sma > 0 else 0.0
        percent_b = (current_price - lower) / (upper - lower) if (upper - lower) > 0 else 0.5

        return {
            "upper": round(upper, 4),
            "middle": round(sma, 4),
            "lower": round(lower, 4),
            "bandwidth_pct": round(bandwidth, 2),
            "percent_b": round(percent_b, 3),
        }

    @staticmethod
    def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Расчет среднего истинного диапазона (ATR)."""
        if len(closes) < period + 1:
            return 0.0

        true_ranges = []
        for i in range(1, len(closes)):
            h = highs[i]
            l = lows[i]
            prev_c = closes[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0

        atr = sum(true_ranges[:period]) / period
        for i in range(period, len(true_ranges)):
            atr = (atr * (period - 1) + true_ranges[i]) / period

        return round(atr, 4)

    @staticmethod
    def analyze_orderbook_imbalance(orderbook: Optional[Dict[str, Any]], depth_levels: int = 20) -> Dict[str, Any]:
        """
        Анализ дисбаланса объемов в стакане (Orderbook Imbalance) из Redis.
        """
        if not orderbook:
            return {"imbalance_ratio": 1.0, "sentiment": "NEUTRAL", "bid_vol": 0.0, "ask_vol": 0.0, "spread": 0.0}

        bids = orderbook.get("bids", [])[:depth_levels]
        asks = orderbook.get("asks", [])[:depth_levels]

        bid_vol = sum(float(size) for _, size in bids)
        ask_vol = sum(float(size) for _, size in asks)

        if ask_vol > 0:
            ratio = round(bid_vol / ask_vol, 3)
        else:
            ratio = 2.0 if bid_vol > 0 else 1.0

        if ratio >= 1.5:
            sentiment = "STRONG_BUY_PRESSURE"
        elif ratio >= 1.15:
            sentiment = "BUY_PRESSURE"
        elif ratio <= 0.65:
            sentiment = "STRONG_SELL_PRESSURE"
        elif ratio <= 0.85:
            sentiment = "SELL_PRESSURE"
        else:
            sentiment = "BALANCED"

        best_bid = float(bids[0][0]) if bids else 0.0
        best_ask = float(asks[0][0]) if asks else 0.0
        spread = round(best_ask - best_bid, 4) if (best_bid and best_ask) else 0.0

        return {
            "imbalance_ratio": ratio,
            "sentiment": sentiment,
            "bid_vol": round(bid_vol, 4),
            "ask_vol": round(ask_vol, 4),
            "spread": spread,
            "best_bid": best_bid,
            "best_ask": best_ask,
        }

    @classmethod
    def analyze_full_market(
        cls,
        klines: List[Any],
        orderbook: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Комплексный расчет всех технических индикаторов по свечам и стакану.
        """
        if not klines or len(klines) < 14:
            return {"status": "insufficient_data", "klines_count": len(klines) if klines else 0}

        closes = [float(k.close if hasattr(k, "close") else k["close"]) for k in klines]
        highs = [float(k.high if hasattr(k, "high") else k["high"]) for k in klines]
        lows = [float(k.low if hasattr(k, "low") else k["low"]) for k in klines]
        volumes = [float(k.volume if hasattr(k, "volume") else k["volume"]) for k in klines]

        current_price = closes[-1]

        # 1. Скользящие средние
        ema9 = cls.calculate_ema(closes, 9)
        ema21 = cls.calculate_ema(closes, 21)
        ema50 = cls.calculate_ema(closes, 50)
        ema200 = cls.calculate_ema(closes, 200)

        val_ema9 = ema9[-1] if ema9 else current_price
        val_ema21 = ema21[-1] if ema21 else current_price
        val_ema50 = ema50[-1] if ema50 else current_price
        val_ema200 = ema200[-1] if ema200 else current_price

        # Определение тренда
        if current_price > val_ema50 > val_ema200:
            trend = "STRONG_BULLISH"
        elif current_price > val_ema21 > val_ema50:
            trend = "BULLISH"
        elif current_price < val_ema50 < val_ema200:
            trend = "STRONG_BEARISH"
        elif current_price < val_ema21 < val_ema50:
            trend = "BEARISH"
        else:
            trend = "CONSOLIDATION"

        # 2. RSI
        rsi = cls.calculate_rsi(closes, 14)
        if rsi >= 70:
            rsi_status = "OVERBOUGHT"
        elif rsi <= 30:
            rsi_status = "OVERSOLD"
        else:
            rsi_status = "NEUTRAL"

        # 3. MACD
        macd = cls.calculate_macd(closes)

        # 4. Bollinger Bands
        bb = cls.calculate_bollinger_bands(closes, 20)

        # 5. ATR
        atr = cls.calculate_atr(highs, lows, closes, 14)

        # 6. Уровни поддержки и сопротивления (локальные экстремумы за 30 свечей)
        lookback = min(30, len(highs))
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        resistance_level = max(recent_highs)
        support_level = min(recent_lows)

        # 7. Дисбаланс стакана (Orderbook Imbalance)
        ob_analysis = cls.analyze_orderbook_imbalance(orderbook)

        # 8. Объемная активность
        avg_vol = sum(volumes[-20:]) / min(20, len(volumes)) if volumes else 1.0
        current_vol = volumes[-1]
        vol_ratio = round(current_vol / avg_vol, 2) if avg_vol > 0 else 1.0

        return {
            "current_price": current_price,
            "trend": trend,
            "ema": {
                "ema9": round(val_ema9, 4),
                "ema21": round(val_ema21, 4),
                "ema50": round(val_ema50, 4),
                "ema200": round(val_ema200, 4),
            },
            "rsi": {
                "value": rsi,
                "status": rsi_status,
            },
            "macd": macd,
            "bollinger_bands": bb,
            "atr": atr,
            "support_level": round(support_level, 4),
            "resistance_level": round(resistance_level, 4),
            "volume_ratio": vol_ratio,
            "orderbook_imbalance": ob_analysis,
        }
