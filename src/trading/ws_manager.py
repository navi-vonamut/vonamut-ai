import time
import queue
import logging
import threading
import datetime
from typing import List, Dict, Any, Optional
from pybit.unified_trading import WebSocket

from src.trading.config import trading_config, TradingConfig
from src.trading.db import get_trading_db, TradingDBManager
from src.trading.redis_client import get_trading_redis, TradingRedisClient

logger = logging.getLogger(__name__)

class BybitWSManager:
    """
    Менеджер WebSocket-соединений Bybit V5.
    Обеспечивает непрерывный стриминг свечей, стакана и сделок:
    1. Мгновенная запись горячих данных в Redis (< 0.5 ms) и публикация событий в Pub/Sub.
    2. Неблокирующая очередь и пакетная фоновая запись в PostgreSQL (Cold Storage).
    """

    def __init__(
        self,
        config: Optional[TradingConfig] = None,
        db_manager: Optional[TradingDBManager] = None,
        redis_client: Optional[TradingRedisClient] = None
    ):
        self.config = config or trading_config
        self.db = db_manager or get_trading_db()
        self.redis = redis_client or get_trading_redis()

        self._queue: queue.Queue = queue.Queue(maxsize=self.config.ws_buffer_max_size)
        self._running = False
        self._writer_thread: Optional[threading.Thread] = None
        self._ws_client: Optional[WebSocket] = None

        # Статистика
        self.stats = {
            "klines_received": 0,
            "orderbooks_received": 0,
            "trades_received": 0,
            "batches_saved_pg": 0,
            "redis_hot_updates": 0,
            "errors": 0,
        }

    def _on_kline_message(self, message: Dict[str, Any]):
        """Callback для свечей из WebSocket."""
        try:
            topic = message.get("topic", "")
            data = message.get("data", [])
            # Topic format: kline.{interval}.{symbol}
            parts = topic.split(".")
            interval = parts[1] if len(parts) >= 3 else "1"
            symbol = parts[2] if len(parts) >= 3 else ""

            for item in data:
                open_ts = int(item.get("start", item.get("timestamp", time.time() * 1000)))
                kline_item = {
                    "type": "kline",
                    "symbol": symbol or item.get("symbol", ""),
                    "interval": str(interval),
                    "open_time": open_ts,
                    "open_time_dt": datetime.datetime.utcfromtimestamp(open_ts / 1000.0),
                    "open": float(item.get("open", 0.0)),
                    "high": float(item.get("high", 0.0)),
                    "low": float(item.get("low", 0.0)),
                    "close": float(item.get("close", 0.0)),
                    "volume": float(item.get("volume", 0.0)),
                    "turnover": float(item.get("turnover", 0.0) or 0.0),
                    "is_closed": bool(item.get("confirm", False)),
                }
                self.stats["klines_received"] += 1

                # ⚡ Hot Path: Мгновенно в Redis
                self.redis.set_kline(kline_item["symbol"], str(interval), kline_item)
                if kline_item["is_closed"]:
                    # Оповещаем ядро агента о закрытии свечи через Pub/Sub
                    self.redis.publish_market_event(
                        channel=f"kline:{kline_item['symbol']}:{interval}",
                        event_data=kline_item
                    )
                self.stats["redis_hot_updates"] += 1

                # 💾 Cold Path: В очередь на сохранение в Postgres
                self._enqueue(kline_item)
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error in _on_kline_message: {e}")

    def _on_orderbook_message(self, message: Dict[str, Any]):
        """Callback для стакана цен из WebSocket."""
        try:
            data = message.get("data", {})
            symbol = data.get("s", "")
            ts_ms = int(message.get("ts", time.time() * 1000))

            bids = [[float(p), float(s)] for p, s in data.get("b", [])]
            asks = [[float(p), float(s)] for p, s in data.get("a", [])]

            if bids or asks:
                snap_item = {
                    "type": "orderbook",
                    "symbol": symbol,
                    "timestamp": ts_ms,
                    "timestamp_dt": datetime.datetime.utcfromtimestamp(ts_ms / 1000.0),
                    "bids": bids,
                    "asks": asks,
                    "update_id": data.get("u"),
                }
                self.stats["orderbooks_received"] += 1

                # ⚡ Hot Path: Мгновенное обновление стакана в Redis
                self.redis.set_orderbook(
                    symbol=symbol,
                    bids=bids,
                    asks=asks,
                    timestamp=ts_ms,
                    update_id=data.get("u")
                )
                self.stats["redis_hot_updates"] += 1

                # 💾 Cold Path: В очередь на сброс в Postgres
                self._enqueue(snap_item)
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error in _on_orderbook_message: {e}")

    def _on_trade_message(self, message: Dict[str, Any]):
        """Callback для потока сделок из WebSocket."""
        try:
            data = message.get("data", [])
            for item in data:
                ts_ms = int(item.get("T", time.time() * 1000))
                trade_item = {
                    "type": "trade",
                    "symbol": item.get("s", ""),
                    "trade_id": str(item.get("i", "")),
                    "price": float(item.get("p", 0.0)),
                    "size": float(item.get("v", 0.0)),
                    "side": str(item.get("S", "Buy")),
                    "timestamp": ts_ms,
                    "timestamp_dt": datetime.datetime.utcfromtimestamp(ts_ms / 1000.0),
                }
                self.stats["trades_received"] += 1

                # ⚡ Hot Path: Скользящее окно сделок в Redis
                self.redis.push_trade(trade_item["symbol"], trade_item)
                self.stats["redis_hot_updates"] += 1

                # 💾 Cold Path: В очередь
                self._enqueue(trade_item)
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error in _on_trade_message: {e}")

    def _enqueue(self, item: Dict[str, Any]):
        """Безопасное добавление в очередь буфера."""
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            logger.warning("WebSocket ingestion queue is full! Dropping oldest item.")
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(item)

    def _batch_writer_loop(self):
        """
        Фоновый цикл пакетной записи накопленных данных в базу PostgreSQL.
        """
        logger.info("Batch DB writer worker started.")
        kline_batch = []
        orderbook_batch = []
        trade_batch = []
        last_flush = time.time()

        while self._running:
            try:
                # Извлекаем элемент с таймаутом
                try:
                    item = self._queue.get(timeout=0.2)
                    item_type = item.get("type")
                    if item_type == "kline":
                        kline_batch.append(item)
                    elif item_type == "orderbook":
                        orderbook_batch.append(item)
                    elif item_type == "trade":
                        trade_batch.append(item)
                    self._queue.task_done()
                except queue.Empty:
                    pass

                now = time.time()
                should_flush = (
                    (now - last_flush >= self.config.db_flush_interval_sec) or
                    (len(kline_batch) + len(orderbook_batch) + len(trade_batch) >= self.config.db_batch_size)
                )

                if should_flush:
                    if kline_batch:
                        self.db.upsert_klines_batch(kline_batch)
                        kline_batch.clear()

                    if orderbook_batch:
                        self.db.insert_orderbook_snapshots_batch(orderbook_batch)
                        orderbook_batch.clear()

                    if trade_batch:
                        self.db.insert_trades_batch(trade_batch)
                        trade_batch.clear()

                    self.stats["batches_saved_pg"] += 1
                    last_flush = now

            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Error in batch writer loop: {e}", exc_info=True)
                time.sleep(0.5)

        # Финальный сброс оставшихся элементов перед завершением
        if kline_batch:
            self.db.upsert_klines_batch(kline_batch)
        if orderbook_batch:
            self.db.insert_orderbook_snapshots_batch(orderbook_batch)
        if trade_batch:
            self.db.insert_trades_batch(trade_batch)
        logger.info("Batch DB writer worker finished.")

    def start(self, symbols: Optional[List[str]] = None, intervals: Optional[List[str]] = None):
        """Запуск WebSocket подписок и воркера базы данных."""
        if self._running:
            logger.warning("BybitWSManager is already running.")
            return

        symbols = symbols or self.config.symbols
        intervals = intervals or self.config.kline_intervals

        # Инициализация таблиц БД и проверка Redis
        self.db.init_db()
        if self.redis.ping():
            logger.info("⚡ Connected to Redis hot cache successfully.")
        else:
            logger.warning("⚠️ Redis hot cache is unreachable, continuing with PG storage only.")

        self._running = True
        self._writer_thread = threading.Thread(target=self._batch_writer_loop, daemon=True)
        self._writer_thread.start()

        # Инициализация pybit WebSocket
        self._ws_client = WebSocket(
            testnet=self.config.testnet,
            channel_type=self.config.category,
            api_key=self.config.api_key if self.config.api_key else None,
            api_secret=self.config.api_secret if self.config.api_secret else None,
        )

        # Подписка на каналы
        for sym in symbols:
            # 1. Kline стримы
            for interval in intervals:
                logger.info(f"Subscribing to kline.{interval}.{sym}")
                self._ws_client.kline_stream(
                    interval=interval,
                    symbol=sym,
                    callback=self._on_kline_message
                )

            # 2. Orderbook стрим
            logger.info(f"Subscribing to orderbook.{self.config.orderbook_depth}.{sym}")
            self._ws_client.orderbook_stream(
                depth=self.config.orderbook_depth,
                symbol=sym,
                callback=self._on_orderbook_message
            )

            # 3. Public Trades стрим
            logger.info(f"Subscribing to publicTrade.{sym}")
            self._ws_client.trade_stream(
                symbol=sym,
                callback=self._on_trade_message
            )

        self.db.log_event(
            component="BybitWSManager",
            message_en=f"WebSocket ingestion started for symbols: {', '.join(symbols)} with Redis hot cache",
            message_ru=f"WebSocket сбор данных запущен для пар: {', '.join(symbols)} с кэшем Redis",
            level="INFO",
            details={"symbols": symbols, "intervals": intervals}
        )
        logger.info(f"BybitWSManager started successfully for symbols: {symbols}")

    def stop(self):
        """Остановка менеджера и сохранение оставшихся данных."""
        logger.info("Stopping BybitWSManager...")
        self._running = False
        if self._ws_client:
            try:
                self._ws_client.exit()
            except Exception as e:
                logger.warning(f"Error during WS exit: {e}")

        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=3.0)

        self.db.log_event(
            component="BybitWSManager",
            message_en="WebSocket ingestion stopped.",
            message_ru="WebSocket сбор данных остановлен.",
            level="INFO",
            details=self.stats
        )
        logger.info(f"BybitWSManager stopped. Stats: {self.stats}")
