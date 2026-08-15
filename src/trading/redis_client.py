import json
import logging
import time
import datetime
from typing import Dict, Any, Optional, List, Tuple
import redis

from src.trading.config import trading_config, TradingConfig

logger = logging.getLogger(__name__)

def _json_dumps(obj: Any) -> str:
    """Безопасная сериализация словарей с datetime и спецтипами в JSON."""
    def _default_serializer(o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, default=_default_serializer)

class TradingRedisClient:
    """
    Высокоскоростной клиент Redis (L1 In-Memory Cache & Pub/Sub) для торгового агента.
    Обеспечивает мгновенный доступ (< 0.5 ms) к актуальному стакану, котировкам и ленте сделок.
    """

    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or trading_config
        self.redis_url = self.config.get_effective_redis_url()
        self.pool = redis.ConnectionPool.from_url(
            self.redis_url,
            decode_responses=True,
            max_connections=20,
            socket_timeout=2.0,
            socket_connect_timeout=2.0
        )
        self.client = redis.Redis(connection_pool=self.pool)

    def ping(self) -> bool:
        """Проверка доступности сервера Redis."""
        try:
            return bool(self.client.ping())
        except Exception as e:
            logger.error(f"Redis ping failed ({self.redis_url}): {e}")
            return False

    def is_connected(self) -> bool:
        """Проверка соединения с Redis."""
        return self.ping()

    # --- Hot Cache: Tickers & Prices ---
    def set_ticker(self, symbol: str, data: Dict[str, Any], ttl_sec: int = 120):
        """Сохранить актуальные данные тикера."""
        key = f"market:ticker:{symbol}"
        try:
            self.client.set(key, _json_dumps(data), ex=ttl_sec)
        except Exception as e:
            logger.warning(f"Error setting ticker in Redis for {symbol}: {e}")

    def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получить данные тикера."""
        key = f"market:ticker:{symbol}"
        try:
            val = self.client.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.warning(f"Error getting ticker from Redis for {symbol}: {e}")
            return None

    # --- Hot Cache: OrderBook ---
    def set_orderbook(
        self,
        symbol: str,
        bids: List[List[float]],
        asks: List[List[float]],
        timestamp: int,
        update_id: Optional[int] = None,
        ttl_sec: int = 60
    ):
        """Сохранить актуальный снимок стакана цен в Redis."""
        key = f"market:orderbook:{symbol}"
        best_bid = bids[0][0] if bids and len(bids[0]) > 0 else 0.0
        best_ask = asks[0][0] if asks and len(asks[0]) > 0 else 0.0
        payload = {
            "symbol": symbol,
            "timestamp": timestamp,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": round(best_ask - best_bid, 4) if (best_bid and best_ask) else 0.0,
            "bids": bids,
            "asks": asks,
            "update_id": update_id,
            "updated_at": time.time(),
        }
        try:
            self.client.set(key, _json_dumps(payload), ex=ttl_sec)
        except Exception as e:
            logger.warning(f"Error setting orderbook in Redis for {symbol}: {e}")

    def get_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получить актуальный стакан из памяти."""
        key = f"market:orderbook:{symbol}"
        try:
            val = self.client.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.warning(f"Error getting orderbook from Redis for {symbol}: {e}")
            return None

    def get_best_bid_ask(self, symbol: str) -> Tuple[float, float]:
        """
        Мгновенное получение Best Bid и Best Ask за < 0.3 ms для Risk Engine.
        """
        ob = self.get_orderbook(symbol)
        if ob:
            return float(ob.get("best_bid", 0.0)), float(ob.get("best_ask", 0.0))
        return 0.0, 0.0

    # --- Hot Cache: Latest Klines ---
    def set_kline(self, symbol: str, interval: str, kline_data: Dict[str, Any], ttl_sec: int = 300):
        """Сохранить состояние текущей свечи."""
        key = f"market:kline:{symbol}:{interval}"
        try:
            self.client.set(key, _json_dumps(kline_data), ex=ttl_sec)
        except Exception as e:
            logger.warning(f"Error setting kline in Redis for {symbol}:{interval}: {e}")

    def get_kline(self, symbol: str, interval: str) -> Optional[Dict[str, Any]]:
        """Получить текущую формирующуюся или последнюю свечу."""
        key = f"market:kline:{symbol}:{interval}"
        try:
            val = self.client.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.warning(f"Error getting kline from Redis for {symbol}:{interval}: {e}")
            return None

    # --- Rolling Trades Window (List) ---
    def push_trade(self, symbol: str, trade_data: Dict[str, Any], max_len: int = 100):
        """Добавить сделку в скользящее окно последних сделок."""
        key = f"market:trades:{symbol}"
        try:
            p = self.client.pipeline()
            p.lpush(key, _json_dumps(trade_data))
            p.ltrim(key, 0, max_len - 1)
            p.execute()
        except Exception as e:
            logger.warning(f"Error pushing trade to Redis for {symbol}: {e}")

    def get_recent_trades(self, symbol: str, count: int = 50) -> List[Dict[str, Any]]:
        """Получить последние N сделок из памяти."""
        key = f"market:trades:{symbol}"
        try:
            items = self.client.lrange(key, 0, count - 1)
            return [json.loads(x) for x in items] if items else []
        except Exception as e:
            logger.warning(f"Error getting recent trades from Redis for {symbol}: {e}")
            return []

    # --- Pub/Sub Event Bus ---
    def publish_market_event(self, channel: str, event_data: Dict[str, Any]) -> int:
        """Опубликовать событие в шину Redis Pub/Sub."""
        try:
            return self.client.publish(f"events:{channel}", _json_dumps(event_data))
        except Exception as e:
            logger.warning(f"Error publishing to channel {channel}: {e}")
            return 0

    # --- Distributed Locks ---
    def acquire_lock(self, lock_name: str, timeout_sec: int = 5) -> Optional[Any]:
        """
        Получение распределенной блокировки для предотвращения гонок при выставлении ордеров.
        """
        try:
            lock = self.client.lock(f"lock:{lock_name}", timeout=timeout_sec, blocking_timeout=1.0)
            if lock.acquire(blocking=True):
                return lock
        except Exception as e:
            logger.error(f"Error acquiring lock {lock_name}: {e}")
        return None

_redis_instance: Optional[TradingRedisClient] = None

def get_trading_redis() -> TradingRedisClient:
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = TradingRedisClient()
    return _redis_instance
