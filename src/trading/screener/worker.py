import time
import json
import logging
import threading
from typing import Optional, Dict, Any, List

from src.trading.redis_client import get_trading_redis, TradingRedisClient
from src.trading.screener.engine import MarketScreener, ScreenerSnapshot
from src.trading.screener.config import screener_config, ScreenerConfig

logger = logging.getLogger(__name__)

REDIS_SCREENER_KEY = "screener:hot_pairs"
REDIS_SCREENER_TTL = 900 # 15 minutes

class ScreenerWorker:
    """
    Фоновый воркер скринера рынка. Периодически опрашивает Bybit,
    сохраняет горячие пары в Redis L1 Hot Cache и уведомляет компоненты.
    """

    def __init__(self, config: Optional[ScreenerConfig] = None):
        self.config = config or screener_config
        self.engine = MarketScreener(config=self.config)
        self.redis: TradingRedisClient = get_trading_redis()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _trigger_rag_news_sync(self, symbols: List[str]):
        """Фоновый запуск сбора новостей и векторизации для горячих монет."""
        try:
            from src.trading.rag import get_rag_service
            rag = get_rag_service()
            rag.sync_hot_movers_news(symbols)
        except Exception as e:
            logger.warning(f"Screener -> RAG news sync error: {e}")

    def run_scan_and_cache(self) -> ScreenerSnapshot:
        """Однократный прогон сканера и кэширование в Redis."""
        snapshot = self.engine.scan_market()
        try:
            if self.redis.is_connected() and self.redis.client:
                data_json = json.dumps(snapshot.model_dump())
                self.redis.client.setex(REDIS_SCREENER_KEY, REDIS_SCREENER_TTL, data_json)
                logger.info(f"Screener snapshot cached in Redis. Hot tickers: {[t.symbol for t in snapshot.tickers]}")
        except Exception as e:
            logger.warning(f"Failed to cache screener snapshot in Redis: {e}")

        # Автоматический запуск сбора новостей по топ-5 горячим монетам
        if snapshot.tickers:
            top_symbols = [t.symbol for t in snapshot.tickers[:5]]
            threading.Thread(
                target=self._trigger_rag_news_sync,
                args=(top_symbols,),
                daemon=True,
                name="HotMoversRAGSync"
            ).start()

        return snapshot

    def get_cached_snapshot(self) -> Optional[Dict[str, Any]]:
        """Получение последнего сохраненного снимка скринера из Redis."""
        try:
            if self.redis.is_connected() and self.redis.client:
                cached = self.redis.client.get(REDIS_SCREENER_KEY)
                if cached:
                    return json.loads(cached)
        except Exception as e:
            logger.debug(f"Redis screener get error: {e}")
        return None

    def _loop(self):
        """Фоновый цикл сканирования."""
        logger.info(f"ScreenerWorker background loop started (interval={self.config.scan_interval_sec}s).")
        while self._running:
            try:
                self.run_scan_and_cache()
            except Exception as e:
                logger.error(f"Error in ScreenerWorker loop: {e}")
            
            # Сон с шагом для быстрой остановки
            for _ in range(self.config.scan_interval_sec):
                if not self._running:
                    break
                time.sleep(1)

    def start_background(self):
        """Запуск фонового потока."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="MarketScreenerWorker")
        self._thread.start()
        logger.info("MarketScreenerWorker thread started.")

    def stop(self):
        """Остановка фонового потока."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
            logger.info("MarketScreenerWorker thread stopped.")

_screener_worker_instance: Optional[ScreenerWorker] = None

def get_screener_worker() -> ScreenerWorker:
    global _screener_worker_instance
    if _screener_worker_instance is None:
        _screener_worker_instance = ScreenerWorker()
    return _screener_worker_instance
