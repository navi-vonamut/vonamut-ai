import time
import threading
import logging
from typing import Optional

from src.trading.execution.lifecycle_manager import get_lifecycle_manager, TradeLifecycleManager

logger = logging.getLogger(__name__)

class PositionLifecycleWorker:
    """
    Фоновый воркер управления открытыми сделками (Breakeven + Trailing Stops + Time-based Exits).
    Запускается в фоновом потоке и каждые 10–15 секунд контролирует состояние позиций.
    """

    def __init__(self, interval_sec: float = 12.0):
        self.interval_sec = interval_sec
        self.manager: TradeLifecycleManager = get_lifecycle_manager()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Запуск фонового потока мониторинга позиций."""
        if self._running:
            logger.warning("PositionLifecycleWorker is already running.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="PositionLifecycleWorker", daemon=True)
        self._thread.start()
        logger.info(f"PositionLifecycleWorker started in background (Polling every {self.interval_sec}s).")

    def stop(self):
        """Остановка фонового потока."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info("PositionLifecycleWorker stopped.")

    def _run_loop(self):
        """Основной цикл воркера."""
        logger.info("PositionLifecycleWorker loop started.")
        while self._running:
            try:
                self.manager.process_positions()
            except Exception as e:
                logger.error(f"Error in PositionLifecycleWorker loop: {e}", exc_info=True)

            # Пауза между проверками
            time.sleep(self.interval_sec)

_lifecycle_worker_instance: Optional[PositionLifecycleWorker] = None

def get_lifecycle_worker() -> PositionLifecycleWorker:
    global _lifecycle_worker_instance
    if _lifecycle_worker_instance is None:
        _lifecycle_worker_instance = PositionLifecycleWorker()
    return _lifecycle_worker_instance
