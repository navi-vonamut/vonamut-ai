import logging
import time
from typing import List, Optional, Dict, Any

from src.trading.config import trading_config, TradingConfig
from src.trading.db import get_trading_db, TradingDBManager
from src.trading.rest_client import BybitRestClient
from src.trading.ws_manager import BybitWSManager

logger = logging.getLogger(__name__)

class DataIngestionService:
    """
    Высокоуровневый сервис сбора рыночных данных Bybit (Этап 1).
    Координирует:
    1. Инициализацию БД.
    2. Проверку соединения с биржей.
    3. Синхронизацию исторического контекста через REST.
    4. Потоковую маршрутизацию свечей, стакана и сделок в PostgreSQL через WebSocket.
    """

    def __init__(
        self,
        config: Optional[TradingConfig] = None,
        db_manager: Optional[TradingDBManager] = None
    ):
        self.config = config or trading_config
        self.db = db_manager or get_trading_db()
        self.rest_client = BybitRestClient(self.config)
        self.ws_manager = BybitWSManager(self.config, self.db)

    def initialize(self):
        """Инициализация таблиц БД и проверка связности."""
        logger.info("Initializing DataIngestionService...")
        self.db.init_db()

        conn_status = self.rest_client.check_connection()
        if conn_status.get("status") != "connected":
            err = conn_status.get("error", "Unknown error")
            logger.error(f"Bybit API connection check failed: {err}")
            self.db.log_event(
                component="DataIngestionService",
                message_en=f"Failed to connect to Bybit API: {err}",
                message_ru=f"Ошибка подключения к Bybit API: {err}",
                level="ERROR"
            )
            return False

        logger.info(f"Connected to Bybit API successfully. Demo mode: {self.config.demo}")
        self.db.log_event(
            component="DataIngestionService",
            message_en=f"Data Ingestion Service initialized. Demo mode: {self.config.demo}",
            message_ru=f"Сервис сбора данных инициализирован. Демо режим: {self.config.demo}",
            level="INFO"
        )
        return True

    def sync_history(
        self,
        symbols: Optional[List[str]] = None,
        intervals: Optional[List[str]] = None,
        days_back: int = 7
    ) -> Dict[str, int]:
        """
        Синхронизация исторических данных свечей за указанный период (дней).
        """
        symbols = symbols or self.config.symbols
        intervals = intervals or self.config.kline_intervals
        results = {}

        logger.info(f"Starting history sync for symbols: {symbols}, intervals: {intervals}, days_back: {days_back}")

        for symbol in symbols:
            for interval in intervals:
                key = f"{symbol}_{interval}"
                try:
                    klines = self.rest_client.fetch_historical_klines_bulk(
                        symbol=symbol,
                        interval=interval,
                        days_back=days_back
                    )
                    saved_count = self.db.upsert_klines_batch(klines)
                    results[key] = saved_count
                    logger.info(f"Synced {saved_count} klines for {key}")
                except Exception as e:
                    logger.error(f"Failed to sync history for {key}: {e}")
                    results[key] = 0

        self.db.log_event(
            component="DataIngestionService",
            message_en=f"Historical sync completed: {sum(results.values())} total klines stored.",
            message_ru=f"Синхронизация истории завершена: сохранено {sum(results.values())} свечей.",
            level="INFO",
            details=results
        )
        return results

    def start_streaming(self, symbols: Optional[List[str]] = None, intervals: Optional[List[str]] = None):
        """Запуск потокового сбора в реальном времени."""
        logger.info("Starting real-time market data streaming...")
        self.ws_manager.start(symbols=symbols, intervals=intervals)

    def stop_streaming(self):
        """Остановка потокового сбора."""
        logger.info("Stopping real-time market data streaming...")
        self.ws_manager.stop()

    def run_full_pipeline(self, days_back: int = 7):
        """
        Полный запуск Этапа 1:
        1. Инициализация и проверка.
        2. Догрузка исторических данных.
        3. Запуск непрерывного WebSocket стриминга.
        """
        if not self.initialize():
            raise RuntimeError("DataIngestionService initialization failed.")

        self.sync_history(days_back=days_back)
        self.start_streaming()

        logger.info("Ingestion service is running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(5)
                logger.info(f"Ingestion Stats: {self.ws_manager.stats}")
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Shutting down...")
        finally:
            self.stop_streaming()
