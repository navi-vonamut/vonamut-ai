import logging
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from src.trading.rest_client import BybitRestClient
from src.trading.screener.config import screener_config, ScreenerConfig

logger = logging.getLogger(__name__)

class ScreenerTickerResult(BaseModel):
    """Результат оценки и скоринга тикера скринером рынка."""
    symbol: str
    last_price: float
    turnover_24h_usd: float
    volume_24h: float
    price_change_24h_pct: float
    price_change_1h_pct: float
    open_interest_usd: float
    oi_change_pct: float
    is_oi_growing: bool
    direction_bias: str # BULLISH, BEARISH, VOLATILE
    score: float
    reason: str

class ScreenerSnapshot(BaseModel):
    """Снимок сканирования рынка."""
    timestamp: int
    scanned_count: int
    passed_count: int
    tickers: List[ScreenerTickerResult]

class MarketScreener:
    """
    Высокопроизводительный движок сканирования рынка Bybit V5.
    Отбирает самые активные и ликвидные деривативы по жестким фильтрам.
    """

    def __init__(self, config: Optional[ScreenerConfig] = None):
        self.config = config or screener_config
        self.rest_client = BybitRestClient()

    def _check_oi_trend(self, symbol: str) -> tuple[bool, float]:
        """
        Проверка тренда открытого интереса (Open Interest) за последние 4 интервала по 15м.
        """
        try:
            res = self.rest_client.client.get_open_interest(
                category=self.config.category,
                symbol=symbol,
                intervalTime="15min",
                limit=4
            )
            items = res.get("result", {}).get("list", [])
            if len(items) >= 2:
                # items[0] - самый свежий, items[-1] - старый
                latest_oi = float(items[0].get("openInterest", 0.0) or 0.0)
                old_oi = float(items[-1].get("openInterest", 0.0) or 0.0)
                if old_oi > 0:
                    delta_pct = round(((latest_oi - old_oi) / old_oi) * 100.0, 2)
                    return (delta_pct > 0), delta_pct
        except Exception as e:
            logger.debug(f"OI trend check notice for {symbol}: {e}")
        return False, 0.0

    def scan_market(self) -> ScreenerSnapshot:
        """
        Полное сканирование всех линейных инструментов Bybit V5.
        """
        t0 = time.time()
        try:
            res = self.rest_client.client.get_tickers(category=self.config.category)
            ticker_list = res.get("result", {}).get("list", [])
        except Exception as e:
            logger.error(f"Failed to fetch market tickers from Bybit: {e}")
            return ScreenerSnapshot(timestamp=int(time.time()), scanned_count=0, passed_count=0, tickers=[])

        candidates: List[ScreenerTickerResult] = []

        for t in ticker_list:
            symbol = t.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue

            try:
                turnover_24h = float(t.get("turnover24h", 0.0) or 0.0)
                last_price = float(t.get("lastPrice", 0.0) or 0.0)
                vol_24h = float(t.get("volume24h", 0.0) or 0.0)
                chg_24h_pct = float(t.get("price24hPcnt", 0.0) or 0.0) * 100.0
                prev_1h = float(t.get("prevPrice1h", 0.0) or 0.0)
                oi_val = float(t.get("openInterestValue", 0.0) or 0.0)

                chg_1h_pct = ((last_price - prev_1h) / prev_1h * 100.0) if prev_1h > 0 else 0.0

                # 1. Фильтр ликвидности: Суточный оборот > $20,000,000
                if turnover_24h < self.config.min_24h_turnover_usd:
                    continue

                # 2. Фильтр волатильности: 24h > 5% ИЛИ 1h > 2%
                has_volatility = (
                    abs(chg_24h_pct) >= self.config.min_24h_change_pct or
                    abs(chg_1h_pct) >= self.config.min_1h_change_pct
                )
                if not has_volatility:
                    continue

                # 3. Фильтр притока капитала (Open Interest)
                is_oi_growing, oi_delta = False, 0.0
                if self.config.check_oi_growth:
                    is_oi_growing, oi_delta = self._check_oi_trend(symbol)

                # Определение направления импульса
                if chg_1h_pct > 1.5 or chg_24h_pct > 6.0:
                    bias = "BULLISH"
                elif chg_1h_pct < -1.5 or chg_24h_pct < -6.0:
                    bias = "BEARISH"
                else:
                    bias = "VOLATILE"

                # Расчет скоринга (Объем в $M + Волатильность + Бонус за рост OI)
                vol_score = min(50.0, (turnover_24h / 1_000_000.0) * 0.5)
                momentum_score = min(40.0, (abs(chg_24h_pct) * 1.5) + (abs(chg_1h_pct) * 3.0))
                oi_score = 15.0 if is_oi_growing else 0.0
                total_score = round(vol_score + momentum_score + oi_score, 2)

                reasons = []
                reasons.append(f"Vol ${turnover_24h / 1_000_000:.1f}M")
                reasons.append(f"24h: {chg_24h_pct:+.2f}%")
                reasons.append(f"1h: {chg_1h_pct:+.2f}%")
                if is_oi_growing:
                    reasons.append(f"OI Growth {oi_delta:+.1f}%")

                candidates.append(
                    ScreenerTickerResult(
                        symbol=symbol,
                        last_price=last_price,
                        turnover_24h_usd=round(turnover_24h, 2),
                        volume_24h=round(vol_24h, 2),
                        price_change_24h_pct=round(chg_24h_pct, 2),
                        price_change_1h_pct=round(chg_1h_pct, 2),
                        open_interest_usd=round(oi_val, 2),
                        oi_change_pct=oi_delta,
                        is_oi_growing=is_oi_growing,
                        direction_bias=bias,
                        score=total_score,
                        reason=" | ".join(reasons)
                    )
                )

            except Exception as e:
                logger.debug(f"Error parsing ticker {symbol}: {e}")
                continue

        # Сортировка по скорингу (наиболее горячие и ликвидные сверху)
        candidates.sort(key=lambda x: x.score, reverse=True)
        top_candidates = candidates[:self.config.top_limit]

        elapsed = round((time.time() - t0) * 1000, 1)
        logger.info(
            f"Market Screener finished in {elapsed}ms. "
            f"Scanned {len(ticker_list)} pairs -> Selected {len(top_candidates)} hot movers."
        )

        return ScreenerSnapshot(
            timestamp=int(time.time()),
            scanned_count=len(ticker_list),
            passed_count=len(candidates),
            tickers=top_candidates
        )

_screener_instance: Optional[MarketScreener] = None

def get_market_screener() -> MarketScreener:
    global _screener_instance
    if _screener_instance is None:
        _screener_instance = MarketScreener()
    return _screener_instance

def get_screener() -> MarketScreener:
    return get_market_screener()
