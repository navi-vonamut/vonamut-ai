import logging
import uuid
from typing import Dict, Any, Optional, List
from pybit.unified_trading import HTTP

from src.trading.config import trading_config, TradingConfig

import time
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

class BybitOrderExecutor:
    """
    Модуль прямого взаимодействия с Bybit Unified Trading API V5.
    Обеспечивает получение баланса, открытых позиций и размещение ордеров
    с атомарно привязанными уровнями Take-Profit и Stop-Loss.
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

    def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """
        Получение баланса, капитала (Equity) и доступной маржи.
        """
        try:
            res = self.client.get_wallet_balance(accountType=account_type)
            if res.get("retCode") != 0:
                logger.error(f"Bybit get_wallet_balance error: {res.get('retMsg')}")
                return {"total_equity": 0.0, "available_margin": 0.0, "raw": res}

            account_list = res.get("result", {}).get("list", [])
            if not account_list:
                return {"total_equity": 0.0, "available_margin": 0.0, "raw": res}

            acc = account_list[0]
            total_equity = float(acc.get("totalEquity", 0.0) or 0.0)
            avail_balance = float(acc.get("totalAvailableBalance", 0.0) or 0.0)
            total_margin = float(acc.get("totalMarginBalance", 0.0) or 0.0)

            # Если totalEquity пуст, проверим баланс в монете USDT
            if total_equity == 0.0:
                for coin in acc.get("coin", []):
                    if coin.get("coin") == "USDT":
                        total_equity = float(coin.get("equity", 0.0) or 0.0)
                        avail_balance = float(coin.get("availableToWithdraw", 0.0) or coin.get("walletBalance", 0.0) or 0.0)
                        break

            return {
                "total_equity": total_equity,
                "available_margin": avail_balance or total_margin or total_equity,
                "total_margin_balance": total_margin,
                "account_type": account_type,
                "raw": acc,
            }
        except Exception as e:
            logger.error(f"Failed to fetch wallet balance from Bybit: {e}")
            return {"total_equity": 0.0, "available_margin": 0.0, "error": str(e)}

    def get_fee_rate(self, symbol: str, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение актуальных комиссий для аккаунта и монеты через GET /v5/account/fee-rate.
        Возвращает makerFeeRate и takerFeeRate, процентные ставки и стоимость round-trip.
        """
        category = category or self.config.category
        maker_rate = 0.0002   # Default Linear VIP0 Maker: 0.02%
        taker_rate = 0.00055  # Default Linear VIP0 Taker: 0.055%

        try:
            # 1. Попытка запроса с категорией
            res = self.client.get_fee_rates(category=category, symbol=symbol)
            if res.get("retCode") == 0:
                fee_list = res.get("result", {}).get("list", [])
                if fee_list:
                    item = fee_list[0]
                    maker_rate = float(item.get("makerFeeRate", maker_rate) or maker_rate)
                    taker_rate = float(item.get("takerFeeRate", taker_rate) or taker_rate)
            else:
                # Fallback к spot ставкам если аккаунт возвращает spot таблицу
                res_spot = self.client.get_fee_rates(category="spot")
                if res_spot.get("retCode") == 0:
                    for s in res_spot.get("result", {}).get("list", []):
                        if s.get("symbol") == symbol:
                            maker_rate = float(s.get("makerFeeRate", maker_rate) or maker_rate)
                            taker_rate = float(s.get("takerFeeRate", taker_rate) or taker_rate)
                            break
        except Exception as e:
            logger.debug(f"Bybit get_fee_rates notice for {symbol} ({category}): {e}. Using standard rates.")

        return {
            "symbol": symbol,
            "category": category,
            "maker_fee_rate": maker_rate,
            "taker_fee_rate": taker_rate,
            "maker_fee_pct": round(maker_rate * 100, 4),
            "taker_fee_pct": round(taker_rate * 100, 4),
            "roundtrip_taker_fee_pct": round(taker_rate * 2 * 100, 4),
        }

    def get_open_positions(self, category: Optional[str] = None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получение списка активных открытых позиций на бирже.
        """
        category = category or self.config.category
        params: Dict[str, Any] = {"category": category, "settleCoin": "USDT"}
        if symbol:
            params["symbol"] = symbol

        try:
            res = self.client.get_positions(**params)
            if res.get("retCode") != 0:
                logger.error(f"Bybit get_positions error: {res.get('retMsg')}")
                return []

            raw_positions = res.get("result", {}).get("list", [])
            open_pos = []
            for p in raw_positions:
                size = float(p.get("size", 0.0) or 0.0)
                if size > 0:
                    open_pos.append({
                        "symbol": p.get("symbol"),
                        "side": p.get("side"), # Buy (Long), Sell (Short)
                        "size": size,
                        "entry_price": float(p.get("avgPrice", 0.0) or 0.0),
                        "mark_price": float(p.get("markPrice", 0.0) or 0.0),
                        "leverage": float(p.get("leverage", 1.0) or 1.0),
                        "unrealised_pnl": float(p.get("unrealisedPnl", 0.0) or 0.0),
                        "cur_realised_pnl": float(p.get("curRealisedPnl", 0.0) or 0.0),
                        "stop_loss": float(p.get("stopLoss", 0.0) or 0.0),
                        "take_profit": float(p.get("takeProfit", 0.0) or 0.0),
                        "position_value": float(p.get("positionValue", 0.0) or 0.0),
                    })
            return open_pos
        except Exception as e:
            logger.error(f"Failed to fetch positions from Bybit: {e}")
            return []

    def set_leverage(self, symbol: str, leverage: int, category: Optional[str] = None) -> bool:
        """Установка плеча для инструмента."""
        category = category or self.config.category
        try:
            res = self.client.set_leverage(
                category=category,
                symbol=symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage)
            )
            # retCode 0 (успех) или 110043 (плечо уже установлено)
            return res.get("retCode") in (0, 110043)
        except Exception as e:
            logger.warning(f"Error setting leverage {leverage}x for {symbol}: {e}")
            return False

    def place_order_with_tpsl(
        self,
        symbol: str,
        side: str, # "Buy" или "Sell"
        qty: float,
        order_type: str = "Market", # "Market" или "Limit"
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        leverage: Optional[int] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Размещение ордера с АТОМАРНЫМ выставлением Take-Profit и Stop-Loss на бирже Bybit V5.
        """
        category = category or self.config.category
        order_link_id = f"agy_{symbol.lower()}_{uuid.uuid4().hex[:8]}"

        # 1. Установка плеча
        if leverage:
            self.set_leverage(symbol, leverage, category=category)

        order_params: Dict[str, Any] = {
            "category": category,
            "symbol": symbol,
            "side": side, # Buy / Sell
            "orderType": order_type,
            "qty": str(qty),
            "orderLinkId": order_link_id,
            "tpslMode": "Full",
            "tpTriggerBy": "LastPrice",
            "slTriggerBy": "LastPrice",
        }

        if order_type.lower() == "limit" and price:
            order_params["price"] = str(price)
            order_params["timeInForce"] = "GTC"

        if stop_loss and stop_loss > 0:
            order_params["stopLoss"] = str(stop_loss)

        if take_profit and take_profit > 0:
            order_params["takeProfit"] = str(take_profit)

        try:
            logger.info(f"Submitting order to Bybit V5: {order_params}")
            res = self.client.place_order(**order_params)
            ret_code = res.get("retCode")
            if ret_code == 0:
                result_data = res.get("result", {})
                order_id = result_data.get("orderId")
                logger.info(f"✅ Order placed successfully on Bybit! OrderID: {order_id}, LinkID: {order_link_id}")
                return {
                    "status": "Submitted",
                    "order_id": order_id,
                    "order_link_id": order_link_id,
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "price": price or 0.0,
                    "sl_price": stop_loss,
                    "tp_price": take_profit,
                    "raw": res,
                }
            else:
                err_msg = res.get("retMsg", "Unknown error")
                logger.error(f"❌ Bybit place_order failed: {err_msg} (code: {ret_code})")
                return {
                    "status": "Rejected",
                    "error": err_msg,
                    "code": ret_code,
                    "order_link_id": order_link_id,
                    "raw": res,
                }
        except Exception as e:
            logger.error(f"Exception while placing order on Bybit: {e}")
            return {
                "status": "Error",
                "error": str(e),
                "order_link_id": order_link_id,
            }

    def set_trading_stop(
        self,
        symbol: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop: Optional[float] = None,
        active_price: Optional[float] = None,
        position_idx: int = 0,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Модификация активных Stop-Loss, Take-Profit и Trailing Stop для открытой позиции (Bybit V5 set_trading_stop).
        """
        category = category or self.config.category
        params: Dict[str, Any] = {
            "category": category,
            "symbol": symbol,
            "positionIdx": position_idx,
            "tpslMode": "Full",
            "slTriggerBy": "MarkPrice",
            "tpTriggerBy": "LastPrice",
        }

        if stop_loss is not None:
            params["stopLoss"] = str(round(stop_loss, 6)) if stop_loss > 0 else "0"

        if take_profit is not None:
            params["takeProfit"] = str(round(take_profit, 6)) if take_profit > 0 else "0"

        if trailing_stop is not None:
            params["trailingStop"] = str(round(trailing_stop, 6)) if trailing_stop > 0 else "0"
            if active_price is not None and active_price > 0:
                params["activePrice"] = str(round(active_price, 6))

        try:
            logger.info(f"Setting trading stop for {symbol}: {params}")
            res = self.client.set_trading_stop(**params)
            ret_code = res.get("retCode")
            if ret_code == 0:
                logger.info(f"✅ Bybit set_trading_stop applied successfully for {symbol}!")
                return {"status": "Success", "raw": res}
            else:
                err_msg = res.get("retMsg", "Unknown error")
                logger.warning(f"Bybit set_trading_stop failed for {symbol}: {err_msg} (code {ret_code})")
                return {"status": "Failed", "error": err_msg, "code": ret_code}
        except Exception as e:
            logger.error(f"Exception setting trading stop for {symbol}: {e}")
            return {"status": "Error", "error": str(e)}

    def close_position(
        self,
        symbol: str,
        side: str, # "Buy" (closes Short) или "Sell" (closes Long)
        qty: float,
        order_type: str = "Market",
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Рыночное закрытие позиции с флагом reduceOnly=True.
        """
        category = category or self.config.category
        order_link_id = f"close_{symbol.lower()}_{uuid.uuid4().hex[:8]}"
        params: Dict[str, Any] = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": str(qty),
            "reduceOnly": True,
            "orderLinkId": order_link_id,
        }

        try:
            logger.info(f"Closing position on Bybit: {params}")
            res = self.client.place_order(**params)
            ret_code = res.get("retCode")
            if ret_code == 0:
                order_id = res.get("result", {}).get("orderId")
                logger.info(f"✅ Position closed successfully for {symbol}! Order ID: {order_id}")
                return {"status": "Closed", "order_id": order_id, "raw": res}
            else:
                err_msg = res.get("retMsg", "Unknown error")
                logger.error(f"❌ Failed to close position for {symbol}: {err_msg} (code: {ret_code})")
                return {"status": "Failed", "error": err_msg, "code": ret_code}
        except Exception as e:
            logger.error(f"Exception closing position for {symbol}: {e}")
            return {"status": "Error", "error": str(e)}

_order_executor_instance: Optional[BybitOrderExecutor] = None

def get_order_executor() -> BybitOrderExecutor:
    global _order_executor_instance
    if _order_executor_instance is None:
        _order_executor_instance = BybitOrderExecutor()
    return _order_executor_instance
