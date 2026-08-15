import logging
import time
import datetime
from typing import List, Dict, Any, Optional
from pybit.unified_trading import HTTP

from src.trading.config import trading_config, TradingConfig

import requests
import pybit._helpers as pybit_helpers

logger = logging.getLogger(__name__)

def sync_bybit_clock(demo: bool = True):
    """Синхронизация локальных часов с сервером Bybit для предотвращения ошибки 10002."""
    try:
        url = "https://api-demo.bybit.com/v5/market/time" if demo else "https://api.bybit.com/v5/market/time"
        r = requests.get(url, timeout=3).json()
        if r.get("retCode") == 0:
            server_ms = int(r["result"]["timeNano"]) // 1_000_000
            local_ms = int(time.time() * 1000)
            offset = server_ms - local_ms
            pybit_helpers.generate_timestamp = lambda: int(time.time() * 1000) + offset
    except Exception as e:
        logger.debug(f"Time sync skipped: {e}")

class BybitRestClient:
    """
    Клиент Bybit V5 REST API для загрузки исторических свечей,
    проверки спецификаций инструментов и статуса соединения.
    """

    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or trading_config
        sync_bybit_clock(demo=self.config.demo)
        self.client = HTTP(
            testnet=self.config.testnet,
            demo=self.config.demo,
            api_key=self.config.api_key if self.config.api_key else None,
            api_secret=self.config.api_secret if self.config.api_secret else None,
            recv_window=20000,
        )

    def check_connection(self) -> Dict[str, Any]:
        """Проверка соединения с API Bybit V5."""
        try:
            res = self.client.get_server_time()
            server_time_ms = int(res.get("timeSecond", 0)) * 1000 or int(res.get("result", {}).get("timeSecond", 0)) * 1000
            if not server_time_ms and "timeNano" in res:
                server_time_ms = int(int(res["timeNano"]) / 1_000_000)
            return {
                "status": "connected",
                "demo": self.config.demo,
                "server_time_ms": server_time_ms,
                "raw": res,
            }
        except Exception as e:
            logger.error(f"Failed to connect to Bybit REST API: {e}")
            return {"status": "error", "error": str(e)}

    def get_instruments_info(self, category: Optional[str] = None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получить информацию об инструментах (мин. объем, шаг цены, плечо)."""
        category = category or self.config.category
        params: Dict[str, Any] = {"category": category}
        if symbol:
            params["symbol"] = symbol

        try:
            res = self.client.get_instruments_info(**params)
            if res.get("retCode") == 0:
                return res.get("result", {}).get("list", [])
            else:
                logger.warning(f"Bybit get_instruments_info retCode != 0: {res.get('retMsg')}")
                return []
        except Exception as e:
            logger.error(f"Error fetching instruments info for {symbol}: {e}")
            return []

    def get_kline(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 200,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить свечи kline с биржи Bybit V5.
        Возвращает нормализованный список словарей.
        """
        category = category or self.config.category
        params: Dict[str, Any] = {
            "category": category,
            "symbol": symbol,
            "interval": str(interval),
            "limit": min(limit, 1000),
        }
        if start_time:
            params["start"] = int(start_time)
        if end_time:
            params["end"] = int(end_time)

        try:
            res = self.client.get_kline(**params)
            if res.get("retCode") != 0:
                logger.error(f"Bybit get_kline error: {res.get('retMsg')} (code {res.get('retCode')})")
                return []

            raw_list = res.get("result", {}).get("list", [])
            # Bybit V5 kline format:
            # [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]
            normalized = []
            for item in raw_list:
                open_ts = int(item[0])
                normalized.append({
                    "symbol": symbol,
                    "interval": str(interval),
                    "open_time": open_ts,
                    "open_time_dt": datetime.datetime.utcfromtimestamp(open_ts / 1000.0),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[5]),
                    "turnover": float(item[6]) if len(item) > 6 else 0.0,
                    "is_closed": True, # исторические свечи считаются закрытыми
                })
            # Сортируем по возрастанию времени
            normalized.sort(key=lambda x: x["open_time"])
            return normalized
        except Exception as e:
            logger.error(f"Exception in get_kline({symbol}, {interval}): {e}")
            return []

    def fetch_historical_klines_bulk(
        self,
        symbol: str,
        interval: str,
        days_back: int = 7,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Выгрузка исторического окна свечей с пагинацией за указанное количество дней.
        """
        category = category or self.config.category
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - (days_back * 24 * 60 * 60 * 1000)

        all_klines: Dict[int, Dict[str, Any]] = {}
        current_end = now_ms
        max_requests = 100 # Ограничение от бесконечного цикла

        logger.info(f"Starting historical backfill for {symbol} ({interval}) for past {days_back} days...")

        for _ in range(max_requests):
            if current_end <= start_ms:
                break

            chunk = self.get_kline(
                symbol=symbol,
                interval=interval,
                start_time=start_ms,
                end_time=current_end,
                limit=200,
                category=category
            )

            if not chunk:
                break

            for k in chunk:
                all_klines[k["open_time"]] = k

            # Минимальный timestamp в полученной пачке
            oldest_ts = chunk[0]["open_time"]
            if oldest_ts >= current_end:
                break

            current_end = oldest_ts - 1
            time.sleep(0.05) # Небольшая пауза для избежания rate limits

        result = sorted(all_klines.values(), key=lambda x: x["open_time"])
        logger.info(f"Backfill finished for {symbol} ({interval}): fetched {len(result)} klines.")
        return result

    def get_orderbook(self, symbol: str, limit: int = 50, category: Optional[str] = None) -> Dict[str, Any]:
        """Получить текущий снимок стакана (REST)."""
        category = category or self.config.category
        try:
            res = self.client.get_orderbook(category=category, symbol=symbol, limit=limit)
            if res.get("retCode") == 0:
                result = res.get("result", {})
                ts_ms = int(result.get("ts", time.time() * 1000))
                return {
                    "symbol": symbol,
                    "timestamp": ts_ms,
                    "timestamp_dt": datetime.datetime.utcfromtimestamp(ts_ms / 1000.0),
                    "bids": [[float(p), float(s)] for p, s in result.get("b", [])],
                    "asks": [[float(p), float(s)] for p, s in result.get("a", [])],
                    "update_id": result.get("u"),
                }
            return {}
        except Exception as e:
            logger.error(f"Error fetching orderbook for {symbol}: {e}")
            return {}
