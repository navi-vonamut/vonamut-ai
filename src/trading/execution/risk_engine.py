import math
import logging
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from src.trading.execution.config import risk_config, RiskConfig

logger = logging.getLogger(__name__)

class RiskValidationResult(BaseModel):
    """Результат проверки и расчета параметров сделки через Risk Engine с учетом комиссий."""
    passed: bool
    reason: str
    symbol: str
    side: str # Buy / Sell
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    net_risk_reward_ratio: float = 0.0
    position_qty: float
    position_value_usd: float
    required_margin_usd: float
    leverage: int
    risk_usd: float
    risk_pct: float
    maker_fee_rate: float = 0.0002
    taker_fee_rate: float = 0.00055
    estimated_fee_open_usd: float = 0.0
    estimated_fee_close_tp_usd: float = 0.0
    estimated_roundtrip_fee_usd: float = 0.0
    estimated_net_profit_tp_usd: float = 0.0
    estimated_total_loss_sl_usd: float = 0.0
    breakeven_distance_usd: float = 0.0
    breakeven_pct: float = 0.0

class RiskEngine:
    """
    Строгий, изолированный от LLM математический модуль риск-менеджмента.
    Не доверяет сырым параметрам языковых моделей и рассчитывает безопасный
    размер позиции, валидирует R:R с вычетом комиссий Bybit, шаг цены и маржинальные лимиты.
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or risk_config

    def _round_step(self, value: float, step: float) -> float:
        """Округление значения по минимальному шагу биржи (tick size / lot step)."""
        if step <= 0:
            return value
        precision = max(0, int(round(-math.log10(step))))
        return round(math.floor(value / step) * step, precision)

    def validate_and_size_position(
        self,
        decision: Dict[str, Any],
        account_equity: float,
        available_margin: float,
        open_positions_count: int,
        instrument_info: Optional[Dict[str, Any]] = None,
        fee_info: Optional[Dict[str, Any]] = None
    ) -> RiskValidationResult:
        """
        Полная проверка торгового сигнала, учет комиссии биржи (GET /v5/account/fee-rate)
        и расчет математически точного объема позиции.
        """
        symbol = str(decision.get("symbol", "BTCUSDT"))
        action = str(decision.get("action", "HOLD")).upper()
        confidence = float(decision.get("confidence", 0.0))

        # Извлечение актуальных комиссий
        maker_rate = float((fee_info or {}).get("maker_fee_rate", 0.0002))
        taker_rate = float((fee_info or {}).get("taker_fee_rate", 0.00055))

        # 1. Проверка действия
        if action not in ("BUY", "SELL"):
            return RiskValidationResult(
                passed=False,
                reason="Action is HOLD or unrecognized. No execution required.",
                symbol=symbol,
                side="None",
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                risk_reward_ratio=0.0,
                net_risk_reward_ratio=0.0,
                position_qty=0.0,
                position_value_usd=0.0,
                required_margin_usd=0.0,
                leverage=1,
                risk_usd=0.0,
                risk_pct=0.0,
                maker_fee_rate=maker_rate,
                taker_fee_rate=taker_rate
            )

        side = "Buy" if action == "BUY" else "Sell"

        # 2. Проверка минимальной уверенности модели
        if confidence < self.config.min_confidence_to_trade:
            return RiskValidationResult(
                passed=False,
                reason=f"Confidence {confidence:.2f} is below minimum required {self.config.min_confidence_to_trade:.2f}",
                symbol=symbol,
                side=side,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                risk_reward_ratio=0.0,
                position_qty=0.0,
                position_value_usd=0.0,
                required_margin_usd=0.0,
                leverage=1,
                risk_usd=0.0,
                risk_pct=0.0
            )

        # 3. Проверка лимита открытых позиций
        if open_positions_count >= self.config.max_open_positions:
            return RiskValidationResult(
                passed=False,
                reason=f"Open positions limit reached ({open_positions_count}/{self.config.max_open_positions})",
                symbol=symbol,
                side=side,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                risk_reward_ratio=0.0,
                position_qty=0.0,
                position_value_usd=0.0,
                required_margin_usd=0.0,
                leverage=1,
                risk_usd=0.0,
                risk_pct=0.0
            )

        # 4. Проверка баланса
        if account_equity <= 0 or available_margin <= 0:
            return RiskValidationResult(
                passed=False,
                reason=f"Insufficient equity (${account_equity:.2f}) or margin (${available_margin:.2f})",
                symbol=symbol,
                side=side,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                risk_reward_ratio=0.0,
                position_qty=0.0,
                position_value_usd=0.0,
                required_margin_usd=0.0,
                leverage=1,
                risk_usd=0.0,
                risk_pct=0.0
            )

        entry_price = float(decision.get("entry_price", 0.0))
        stop_loss = float(decision.get("stop_loss", 0.0))
        take_profit = float(decision.get("take_profit_1", decision.get("take_profit", 0.0)))
        leverage = min(int(decision.get("recommended_leverage", self.config.default_leverage)), self.config.max_leverage)

        # 5. Проверка логики расположения Stop-Loss и Take-Profit
        if action == "BUY":
            if not (stop_loss < entry_price < take_profit):
                return RiskValidationResult(
                    passed=False,
                    reason=f"Invalid Long levels: SL ({stop_loss}) must be < Entry ({entry_price}) < TP ({take_profit})",
                    symbol=symbol,
                    side=side,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    risk_reward_ratio=0.0,
                    position_qty=0.0,
                    position_value_usd=0.0,
                    required_margin_usd=0.0,
                    leverage=leverage,
                    risk_usd=0.0,
                    risk_pct=0.0
                )
            risk_dist = entry_price - stop_loss
            reward_dist = take_profit - entry_price
        else: # SELL (Short)
            if not (take_profit < entry_price < stop_loss):
                return RiskValidationResult(
                    passed=False,
                    reason=f"Invalid Short levels: TP ({take_profit}) must be < Entry ({entry_price}) < SL ({stop_loss})",
                    symbol=symbol,
                    side=side,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    risk_reward_ratio=0.0,
                    position_qty=0.0,
                    position_value_usd=0.0,
                    required_margin_usd=0.0,
                    leverage=leverage,
                    risk_usd=0.0,
                    risk_pct=0.0
                )
            risk_dist = stop_loss - entry_price
            reward_dist = entry_price - take_profit

        # 6. Проверка соотношения Risk / Reward
        calc_rr = reward_dist / risk_dist if risk_dist > 0 else 0.0
        if calc_rr < self.config.min_risk_reward_ratio:
            return RiskValidationResult(
                passed=False,
                reason=f"Risk/Reward ratio {calc_rr:.2f} is below minimum allowed {self.config.min_risk_reward_ratio:.2f}",
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=round(calc_rr, 2),
                position_qty=0.0,
                position_value_usd=0.0,
                required_margin_usd=0.0,
                leverage=leverage,
                risk_usd=0.0,
                risk_pct=0.0
            )

        # 7. Расчет объема позиции (Position Sizing)
        risk_usd = account_equity * (self.config.max_risk_per_trade_pct / 100.0)
        raw_qty = risk_usd / risk_dist if risk_dist > 0 else 0.0

        # Ограничение по максимальной марже на позицию
        max_position_val_usd = account_equity * (self.config.max_account_margin_usage_pct / 100.0) * leverage
        max_qty_by_margin = max_position_val_usd / entry_price if entry_price > 0 else 0.0

        position_qty = min(raw_qty, max_qty_by_margin)

        # 8. Спецификации инструмента (Lot Size, Step, Min Qty)
        if instrument_info:
            lot_filter = instrument_info.get("lotSizeFilter", {})
            min_qty = float(lot_filter.get("minOrderQty", 0.001))
            max_qty = float(lot_filter.get("maxOrderQty", 10000.0))
            qty_step = float(lot_filter.get("qtyStep", 0.001))

            price_filter = instrument_info.get("priceFilter", {})
            tick_size = float(price_filter.get("tickSize", 0.1))

            # Округление цены и стопов
            entry_price = self._round_step(entry_price, tick_size)
            stop_loss = self._round_step(stop_loss, tick_size)
            take_profit = self._round_step(take_profit, tick_size)

            # Округление объема
            position_qty = self._round_step(position_qty, qty_step)

            if position_qty < min_qty:
                return RiskValidationResult(
                    passed=False,
                    reason=f"Calculated size {position_qty} is below Bybit min lot {min_qty} for {symbol}",
                    symbol=symbol,
                    side=side,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    risk_reward_ratio=round(calc_rr, 2),
                    position_qty=position_qty,
                    position_value_usd=0.0,
                    required_margin_usd=0.0,
                    leverage=leverage,
                    risk_usd=risk_usd,
                    risk_pct=self.config.max_risk_per_trade_pct
                )
            position_qty = min(position_qty, max_qty)

        position_value_usd = position_qty * entry_price
        required_margin_usd = position_value_usd / leverage if leverage > 0 else position_value_usd

        # 9. Проверка доступности маржи
        if required_margin_usd > available_margin:
            return RiskValidationResult(
                passed=False,
                reason=f"Required margin ${required_margin_usd:.2f} exceeds available margin ${available_margin:.2f}",
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=round(calc_rr, 2),
                net_risk_reward_ratio=0.0,
                position_qty=position_qty,
                position_value_usd=round(position_value_usd, 2),
                required_margin_usd=round(required_margin_usd, 2),
                leverage=leverage,
                risk_usd=risk_usd,
                risk_pct=self.config.max_risk_per_trade_pct,
                maker_fee_rate=maker_rate,
                taker_fee_rate=taker_rate
            )

        # 10. Точный расчет комиссий биржи и чистого PnL (Net PnL & Net R:R)
        open_fee_usd = position_value_usd * taker_rate
        close_fee_tp_usd = (take_profit * position_qty) * taker_rate
        roundtrip_fee_tp_usd = open_fee_usd + close_fee_tp_usd

        gross_profit_usd = reward_dist * position_qty
        net_profit_tp_usd = gross_profit_usd - roundtrip_fee_tp_usd

        close_fee_sl_usd = (stop_loss * position_qty) * taker_rate
        total_loss_sl_usd = (risk_dist * position_qty) + open_fee_usd + close_fee_sl_usd

        net_rr = round(net_profit_tp_usd / total_loss_sl_usd, 2) if total_loss_sl_usd > 0 else 0.0
        breakeven_distance_usd = entry_price * (taker_rate * 2)
        breakeven_pct = round(taker_rate * 2 * 100, 4)

        # 11. Защита от отрицательного PnL из-за комиссии
        if net_profit_tp_usd <= 0:
            return RiskValidationResult(
                passed=False,
                reason=f"Trade rejected by Fee Protection: Expected gross profit ${gross_profit_usd:.2f} is eaten by exchange fees ${roundtrip_fee_tp_usd:.2f} (Net PnL: -${abs(net_profit_tp_usd):.2f})",
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=round(calc_rr, 2),
                net_risk_reward_ratio=net_rr,
                position_qty=position_qty,
                position_value_usd=round(position_value_usd, 2),
                required_margin_usd=round(required_margin_usd, 2),
                leverage=leverage,
                risk_usd=risk_usd,
                risk_pct=self.config.max_risk_per_trade_pct,
                maker_fee_rate=maker_rate,
                taker_fee_rate=taker_rate,
                estimated_fee_open_usd=round(open_fee_usd, 4),
                estimated_fee_close_tp_usd=round(close_fee_tp_usd, 4),
                estimated_roundtrip_fee_usd=round(roundtrip_fee_tp_usd, 4),
                estimated_net_profit_tp_usd=round(net_profit_tp_usd, 2),
                estimated_total_loss_sl_usd=round(total_loss_sl_usd, 2),
                breakeven_distance_usd=round(breakeven_distance_usd, 2),
                breakeven_pct=breakeven_pct,
            )

        if net_rr < self.config.min_risk_reward_ratio:
            return RiskValidationResult(
                passed=False,
                reason=f"Net Risk/Reward after fees ({net_rr:.2f}) is below required minimum ({self.config.min_risk_reward_ratio:.2f})",
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=round(calc_rr, 2),
                net_risk_reward_ratio=net_rr,
                position_qty=position_qty,
                position_value_usd=round(position_value_usd, 2),
                required_margin_usd=round(required_margin_usd, 2),
                leverage=leverage,
                risk_usd=risk_usd,
                risk_pct=self.config.max_risk_per_trade_pct,
                maker_fee_rate=maker_rate,
                taker_fee_rate=taker_rate,
                estimated_fee_open_usd=round(open_fee_usd, 4),
                estimated_fee_close_tp_usd=round(close_fee_tp_usd, 4),
                estimated_roundtrip_fee_usd=round(roundtrip_fee_tp_usd, 4),
                estimated_net_profit_tp_usd=round(net_profit_tp_usd, 2),
                estimated_total_loss_sl_usd=round(total_loss_sl_usd, 2),
                breakeven_distance_usd=round(breakeven_distance_usd, 2),
                breakeven_pct=breakeven_pct,
            )

        # Все проверки успешно пройдены!
        return RiskValidationResult(
            passed=True,
            reason="All risk & fee parameters validated successfully.",
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=round(calc_rr, 2),
            net_risk_reward_ratio=net_rr,
            position_qty=position_qty,
            position_value_usd=round(position_value_usd, 2),
            required_margin_usd=round(required_margin_usd, 2),
            leverage=leverage,
            risk_usd=round(position_qty * risk_dist, 2),
            risk_pct=round((position_qty * risk_dist / account_equity) * 100.0, 2),
            maker_fee_rate=maker_rate,
            taker_fee_rate=taker_rate,
            estimated_fee_open_usd=round(open_fee_usd, 4),
            estimated_fee_close_tp_usd=round(close_fee_tp_usd, 4),
            estimated_roundtrip_fee_usd=round(roundtrip_fee_tp_usd, 4),
            estimated_net_profit_tp_usd=round(net_profit_tp_usd, 2),
            estimated_total_loss_sl_usd=round(total_loss_sl_usd, 2),
            breakeven_distance_usd=round(breakeven_distance_usd, 2),
            breakeven_pct=breakeven_pct,
        )
