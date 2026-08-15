import time
import logging
import datetime
from typing import Dict, Any, List, Optional

from src.trading.execution.config import risk_config, RiskConfig
from src.trading.db import get_trading_db, TradingDBManager
from src.trading.redis_client import get_trading_redis, TradingRedisClient
from src.trading.execution.order_executor import get_order_executor, BybitOrderExecutor
from src.trading.execution.models import TradingPosition, TradingOrder

logger = logging.getLogger(__name__)

REDIS_ACTIVE_POSITIONS_KEY = "trading:active_positions"

class TradeLifecycleManager:
    """
    Менеджер жизненного цикла сделок (Trade Lifecycle & Trailing Stop Engine):
    1. Перевод в безубыток (Breakeven): при профите >= +2.0% Stop-Loss переносится на Entry + 0.1% (покрывая комиссии).
    2. Скользящий стоп (Trailing Stop): при профите >= +3.5% стоп подтягивается с шагом 1.5%, выжимая пампы.
    3. Выход по таймауту (Time-Based Exit): если прошло 4 часа и цена находится во флэте (|PnL%| < 0.8%), позиция закрывается.
    """

    def __init__(
        self,
        db: Optional[TradingDBManager] = None,
        redis_client: Optional[TradingRedisClient] = None,
        executor: Optional[BybitOrderExecutor] = None,
        breakeven_pct: float = 0.02, # +2.0%
        fee_cushion_pct: float = 0.001, # +0.1% для комиссии
        trailing_activation_pct: float = 0.035, # +3.5%
        trailing_distance_pct: float = 0.015, # 1.5% от пика
        time_exit_hours: float = 4.0, # 4 часа
        flat_pnl_threshold_pct: float = 0.008, # 0.8%
    ):
        self.db = db or get_trading_db()
        self.redis = redis_client or get_trading_redis()
        self.executor = executor or get_order_executor()
        self.breakeven_pct = breakeven_pct
        self.fee_cushion_pct = fee_cushion_pct
        self.trailing_activation_pct = trailing_activation_pct
        self.trailing_distance_pct = trailing_distance_pct
        self.time_exit_hours = time_exit_hours
        self.flat_pnl_threshold_pct = flat_pnl_threshold_pct

        # Внутренний трекер пиковых цен позиций: {symbol_side: max_price / min_price}
        self._peak_prices: Dict[str, float] = {}
        # Трекер статуса безубытка: {symbol_side: bool}
        self._breakeven_applied: Dict[str, bool] = {}

    def process_positions(self, is_dry_run: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        Главный метод цикла мониторинга. Опрашивает открытые позиции и выполняет действия.
        """
        dry_run = risk_config.dry_run if is_dry_run is None else is_dry_run
        open_positions = self.executor.get_open_positions()

        results = []
        for pos in open_positions:
            res = self.evaluate_position(pos, is_dry_run=dry_run)
            if res:
                results.append(res)

        return results

    def evaluate_position(self, pos: Dict[str, Any], is_dry_run: bool = True) -> Optional[Dict[str, Any]]:
        """
        Оценка одной открытой позиции и применение правил (Breakeven, Trailing, Time-exit).
        """
        symbol = pos.get("symbol", "")
        side = pos.get("side", "") # "Buy" (Long) или "Sell" (Short)
        size = float(pos.get("size", 0.0) or 0.0)
        entry_price = float(pos.get("entry_price", 0.0) or 0.0)
        mark_price = float(pos.get("mark_price", 0.0) or 0.0)
        current_sl = float(pos.get("stop_loss", 0.0) or 0.0)
        current_tp = float(pos.get("take_profit", 0.0) or 0.0)

        if size <= 0 or entry_price <= 0 or mark_price <= 0:
            return None

        pos_key = f"{symbol}_{side}"

        # Расчет нереализованной доходности в %
        if side == "Buy":
            pnl_pct = (mark_price - entry_price) / entry_price
            peak = max(self._peak_prices.get(pos_key, entry_price), mark_price)
            self._peak_prices[pos_key] = peak
        else: # Sell (Short)
            pnl_pct = (entry_price - mark_price) / entry_price
            peak = min(self._peak_prices.get(pos_key, entry_price), mark_price)
            self._peak_prices[pos_key] = peak

        pnl_pct_display = round(pnl_pct * 100, 2)

        # -------------------------------------------------------------
        # ПРАВИЛО 1: Перевод в безубыток (Breakeven) при PnL >= +2.0%
        # -------------------------------------------------------------
        if pnl_pct >= self.breakeven_pct and not self._breakeven_applied.get(pos_key, False):
            if side == "Buy":
                new_sl = round(entry_price * (1.0 + self.fee_cushion_pct), 6)
                if current_sl < new_sl:
                    self._apply_stop_update(symbol, side, new_sl, current_tp, "BREAKEVEN", f"PnL +{pnl_pct_display}% >= +2%", is_dry_run)
                    self._breakeven_applied[pos_key] = True
                    return {"action": "BREAKEVEN_APPLIED", "symbol": symbol, "new_sl": new_sl, "pnl_pct": pnl_pct_display}
            else: # Short
                new_sl = round(entry_price * (1.0 - self.fee_cushion_pct), 6)
                if current_sl == 0 or current_sl > new_sl:
                    self._apply_stop_update(symbol, side, new_sl, current_tp, "BREAKEVEN", f"PnL +{pnl_pct_display}% >= +2%", is_dry_run)
                    self._breakeven_applied[pos_key] = True
                    return {"action": "BREAKEVEN_APPLIED", "symbol": symbol, "new_sl": new_sl, "pnl_pct": pnl_pct_display}

        # -------------------------------------------------------------
        # ПРАВИЛО 2: Динамический Trailing Stop при PnL >= +3.5%
        # -------------------------------------------------------------
        if pnl_pct >= self.trailing_activation_pct:
            if side == "Buy":
                trailing_sl = round(peak * (1.0 - self.trailing_distance_pct), 6)
                # Двигаем стоп только вверх
                if trailing_sl > current_sl:
                    self._apply_stop_update(symbol, side, trailing_sl, current_tp, "TRAILING_STOP", f"Peak ${peak:.4f}, Trail SL ${trailing_sl:.4f} (+{pnl_pct_display}%)", is_dry_run)
                    return {"action": "TRAILING_UPDATED", "symbol": symbol, "new_sl": trailing_sl, "pnl_pct": pnl_pct_display}
            else: # Short
                trailing_sl = round(peak * (1.0 + self.trailing_distance_pct), 6)
                # Двигаем стоп только вниз для шорта
                if current_sl == 0 or trailing_sl < current_sl:
                    self._apply_stop_update(symbol, side, trailing_sl, current_tp, "TRAILING_STOP", f"Trough ${peak:.4f}, Trail SL ${trailing_sl:.4f} (+{pnl_pct_display}%)", is_dry_run)
                    return {"action": "TRAILING_UPDATED", "symbol": symbol, "new_sl": trailing_sl, "pnl_pct": pnl_pct_display}

        return None

    def check_time_based_exit(self, position_row: TradingPosition, current_mark_price: float, is_dry_run: bool = True) -> Optional[Dict[str, Any]]:
        """
        ПРАВИЛО 3: Закрытие по таймауту (Time-based Exit) при удержании >= 4 часов во флэте.
        """
        if not position_row or position_row.status != "OPEN":
            return None

        now = datetime.datetime.utcnow()
        created_at = position_row.created_at or now
        duration_hours = (now - created_at).total_seconds() / 3600.0

        if duration_hours >= self.time_exit_hours:
            entry_price = float(position_row.entry_price)
            if entry_price <= 0 or current_mark_price <= 0:
                return None

            side = position_row.side
            if side in ("Buy", "BUY"):
                pnl_pct = abs(current_mark_price - entry_price) / entry_price
                close_side = "Sell"
            else:
                pnl_pct = abs(entry_price - current_mark_price) / entry_price
                close_side = "Buy"

            # Если цена никуда не ушла (|PnL%| < 0.8%)
            if pnl_pct < self.flat_pnl_threshold_pct:
                symbol = position_row.symbol
                qty = float(position_row.size)
                logger.info(f"⏳ Time-based Exit triggered for {symbol}: held for {duration_hours:.1f}h in flat (|PnL| = {pnl_pct*100:.2f}% < 0.8%). Closing...")

                if is_dry_run:
                    close_res = {"status": "Simulated_Closed", "symbol": symbol, "qty": qty}
                else:
                    close_res = self.executor.close_position(symbol=symbol, side=close_side, qty=qty)

                # Логирование
                self.db.log_event(
                    component="LifecycleManager",
                    message_en=f"Time-based exit executed for {symbol} after {duration_hours:.1f}h (flat PnL {pnl_pct*100:.2f}%). Margin released.",
                    message_ru=f"Выход по таймауту выполнен для {symbol} спустя {duration_hours:.1f}ч (флэт PnL {pnl_pct*100:.2f}%). Маржа освобождена.",
                    level="TIME_EXIT",
                    details=close_res
                )
                return {"action": "TIME_EXIT_EXECUTED", "symbol": symbol, "duration_hours": duration_hours, "result": close_res}

        return None

    def _apply_stop_update(
        self,
        symbol: str,
        side: str,
        new_sl: float,
        current_tp: float,
        reason_type: str,
        reason_desc: str,
        is_dry_run: bool
    ):
        """Вспомогательный метод обновления стопа на бирже и логирования."""
        logger.info(f"🎯 [{reason_type}] Updating Stop-Loss for {symbol} ({side}) to ${new_sl:.4f}. Reason: {reason_desc}")

        if not is_dry_run:
            self.executor.set_trading_stop(
                symbol=symbol,
                stop_loss=new_sl,
                take_profit=current_tp if current_tp > 0 else None
            )

        self.db.log_event(
            component="LifecycleManager",
            message_en=f"[{'DRY-RUN' if is_dry_run else 'LIVE'}] {reason_type}: Moved Stop-Loss for {symbol} ({side}) to ${new_sl:.4f}. ({reason_desc})",
            message_ru=f"[{'СИМУЛЯЦИЯ' if is_dry_run else 'РЕАЛ'}] {reason_type}: Перенос Stop-Loss для {symbol} ({side}) на ${new_sl:.4f}. ({reason_desc})",
            level="STOP_MODIFIED",
            details={"symbol": symbol, "side": side, "new_sl": new_sl, "reason": reason_desc}
        )

        try:
            from src.trading.telegram import get_telegram_notifier
            notifier = get_telegram_notifier()
            if reason_type == "BREAKEVEN":
                notifier.notify_breakeven(symbol, side, new_sl, pnl_pct=2.0, is_dry_run=is_dry_run)
            elif reason_type == "TRAILING_STOP":
                notifier.notify_trailing(symbol, side, new_sl, pnl_pct=3.5, is_dry_run=is_dry_run)
        except Exception as _te:
            logger.debug(f"Telegram notify error: {_te}")

_lifecycle_manager_instance: Optional[TradeLifecycleManager] = None

def get_lifecycle_manager() -> TradeLifecycleManager:
    global _lifecycle_manager_instance
    if _lifecycle_manager_instance is None:
        _lifecycle_manager_instance = TradeLifecycleManager()
    return _lifecycle_manager_instance
