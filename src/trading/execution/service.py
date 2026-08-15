import time
import logging
import datetime
from typing import Dict, Any, Optional, List

from src.trading.execution.config import risk_config, RiskConfig
from src.trading.execution.models import TradingOrder, TradingPosition
from src.trading.execution.risk_engine import RiskEngine, RiskValidationResult
from src.trading.execution.order_executor import BybitOrderExecutor, get_order_executor
from src.trading.rest_client import BybitRestClient
from src.trading.db import get_trading_db, TradingDBManager
from src.trading.redis_client import get_trading_redis, TradingRedisClient

logger = logging.getLogger(__name__)

class ExecutionService:
    """
    Высокоуровневый сервис исполнения сделок и контроля рисков.
    Объединяет:
    1. Расчет рисков и сайзинга через RiskEngine.
    2. Размещение защищенных ордеров на Bybit Unified V5 с TP/SL.
    3. Персистентность ордеров и позиций в PostgreSQL.
    4. Защиту от гонок через распределенные блокировки Redis.
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        db_manager: Optional[TradingDBManager] = None,
        executor: Optional[BybitOrderExecutor] = None,
        redis_client: Optional[TradingRedisClient] = None
    ):
        self.config = config or risk_config
        self.db = db_manager or get_trading_db()
        self.executor = executor or get_order_executor()
        self.redis = redis_client or get_trading_redis()
        self.risk_engine = RiskEngine(self.config)
        self.rest_client = BybitRestClient()

    def initialize(self):
        """Инициализация таблиц ордеров и позиций в PostgreSQL."""
        self.db.init_db()
        logger.info("ExecutionService initialized.")

    def get_wallet_summary(self) -> Dict[str, Any]:
        """Сводка по балансу и марже аккаунта."""
        return self.executor.get_wallet_balance()

    def get_positions_summary(self) -> List[Dict[str, Any]]:
        """Список открытых позиций."""
        return self.executor.get_open_positions()

    def process_and_execute_signal(
        self,
        decision: Dict[str, Any],
        dry_run: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Полный цикл: Валидация решения через Risk Engine ➡️ Блокировка ➡️ Исполнение на Bybit ➡️ Запись в БД.
        """
        is_dry_run = self.config.dry_run if dry_run is None else dry_run
        symbol = decision.get("symbol", "BTCUSDT")

        # 1. Получение баланса
        wallet = self.executor.get_wallet_balance()
        account_equity = wallet.get("total_equity", 0.0)
        available_margin = wallet.get("available_margin", 0.0)

        # Если баланс тестнета 0 или не загружен, для симуляции задаем виртуальный депозит $10,000
        if account_equity <= 0 and is_dry_run:
            account_equity = 10000.0
            available_margin = 10000.0
            logger.info(f"Using simulated equity ${account_equity} for Dry-Run testing.")

        # 2. Получение открытых позиций
        open_positions = self.executor.get_open_positions()
        open_positions_count = len(open_positions)

        # 3. Спецификации инструмента (шаг лота, тик цены) и актуальные комиссии
        instrument_info = None
        info_list = self.rest_client.get_instruments_info(symbol=symbol)
        if info_list:
            instrument_info = info_list[0]

        fee_info = self.executor.get_fee_rate(symbol=symbol)

        # 4. Проверка и расчет объема через Risk Engine (с защитой от комиссий)
        risk_result: RiskValidationResult = self.risk_engine.validate_and_size_position(
            decision=decision,
            account_equity=account_equity,
            available_margin=available_margin,
            open_positions_count=open_positions_count,
            instrument_info=instrument_info,
            fee_info=fee_info
        )

        if not risk_result.passed:
            logger.info(f"Risk Engine Rejected Trade for {symbol}: {risk_result.reason}")
            self.db.log_event(
                component="RiskEngine",
                message_en=f"Trade rejected for {symbol}: {risk_result.reason}",
                message_ru=f"Сделка отклонена Risk Engine для {symbol}: {risk_result.reason}",
                level="INFO",
                details=risk_result.model_dump()
            )
            return {
                "status": "Rejected",
                "risk_validation": risk_result.model_dump(),
                "executed": False
            }

        # 5. Захват распределенной блокировки в Redis
        lock = self.redis.acquire_lock(f"order:{symbol}", timeout_sec=5)
        if not lock:
            msg = f"Order for {symbol} is already being processed (Redis lock acquired by another worker)."
            logger.warning(msg)
            return {"status": "Locked", "error": msg, "executed": False}

        try:
            # 6. Исполнение ордера
            if is_dry_run:
                # Режим симуляции (Dry-Run)
                logger.info(f"🧪 [DRY-RUN] Simulating {risk_result.side} order for {risk_result.position_qty} {symbol} @ {risk_result.entry_price}")
                order_link_id = f"sim_{symbol.lower()}_{int(time.time())}"
                execution_res = {
                    "status": "Simulated",
                    "order_id": f"sim_order_{int(time.time())}",
                    "order_link_id": order_link_id,
                    "symbol": symbol,
                    "side": risk_result.side,
                    "qty": risk_result.position_qty,
                    "price": risk_result.entry_price,
                    "sl_price": risk_result.stop_loss,
                    "tp_price": risk_result.take_profit,
                }
            else:
                # Боевое размещение ордера на Bybit
                execution_res = self.executor.place_order_with_tpsl(
                    symbol=symbol,
                    side=risk_result.side,
                    qty=risk_result.position_qty,
                    order_type="Market", # или Limit
                    price=risk_result.entry_price,
                    stop_loss=risk_result.stop_loss,
                    take_profit=risk_result.take_profit,
                    leverage=risk_result.leverage
                )

            # 7. Сохранение в таблицу trading_orders
            with self.db.get_session() as session:
                order_row = TradingOrder(
                    order_id=execution_res.get("order_id"),
                    order_link_id=execution_res.get("order_link_id"),
                    symbol=symbol,
                    side=risk_result.side,
                    order_type="Market",
                    price=risk_result.entry_price,
                    qty=risk_result.position_qty,
                    sl_price=risk_result.stop_loss,
                    tp_price=risk_result.take_profit,
                    status=execution_res.get("status", "Created"),
                    is_dry_run=is_dry_run,
                    details={
                        "risk_validation": risk_result.model_dump(),
                        "execution_response": execution_res
                    },
                    created_at=datetime.datetime.utcnow(),
                    updated_at=datetime.datetime.utcnow(),
                )
                session.add(order_row)
                session.commit()

            # 8. Логирование события и отправка Telegram push-уведомления
            action_desc = f"{risk_result.side} {risk_result.position_qty} {symbol} @ {risk_result.entry_price}"
            self.db.log_event(
                component="ExecutionService",
                message_en=f"[{'DRY-RUN' if is_dry_run else 'LIVE'}] Order placed: {action_desc}. SL: {risk_result.stop_loss}, TP: {risk_result.take_profit}",
                message_ru=f"[{'СИМУЛЯЦИЯ' if is_dry_run else 'РЕАЛ'}] Ордер размещен: {action_desc}. SL: {risk_result.stop_loss}, TP: {risk_result.take_profit}",
                level="ORDER_PLACED",
                details=execution_res
            )

            try:
                from src.trading.telegram import get_telegram_notifier
                get_telegram_notifier().notify_order_opened({
                    "symbol": symbol,
                    "side": risk_result.side,
                    "qty": risk_result.position_qty,
                    "price": risk_result.entry_price,
                    "sl_price": risk_result.stop_loss,
                    "tp_price": risk_result.take_profit,
                    "net_rr": risk_result.net_risk_reward_ratio or risk_result.risk_reward_ratio,
                }, is_dry_run=is_dry_run)
            except Exception as _te:
                logger.debug(f"Telegram notify error: {_te}")

            return {
                "status": execution_res.get("status"),
                "risk_validation": risk_result.model_dump(),
                "execution": execution_res,
                "is_dry_run": is_dry_run,
                "executed": execution_res.get("status") in ("Submitted", "Simulated")
            }

        finally:
            try:
                lock.release()
            except Exception:
                pass

_execution_service_instance: Optional[ExecutionService] = None

def get_execution_service() -> ExecutionService:
    global _execution_service_instance
    if _execution_service_instance is None:
        _execution_service_instance = ExecutionService()
    return _execution_service_instance
