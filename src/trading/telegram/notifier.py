import logging
import threading
from typing import Optional, Dict, Any
import httpx

from src.trading.telegram.config import telegram_config, TelegramConfig

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    Шлюз отправки push-уведомлений и алертов в Telegram чат/канал.
    Работает асинхронно и в фоновых потоках без блокировки торгового ядра.
    """

    def __init__(self, config: Optional[TelegramConfig] = None):
        self.config = config or telegram_config

    def is_configured(self) -> bool:
        return bool(self.config.bot_token and self.config.admin_chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Синхронная отправка сообщения в Telegram (фоновый запуск потока)."""
        if not self.is_configured() or not self.config.alerts_enabled:
            logger.debug("Telegram notifications are not configured or disabled.")
            return False

        # Отправка в отдельном легком потоке без ожидания
        t = threading.Thread(target=self._send_raw, args=(text, parse_mode), daemon=True)
        t.start()
        return True

    def _send_raw(self, text: str, parse_mode: str = "HTML"):
        try:
            url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
            payload = {
                "chat_id": self.config.admin_chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }
            with httpx.Client(timeout=6.0) as client:
                res = client.post(url, json=payload)
                if res.status_code != 200:
                    logger.warning(f"Telegram alert send failed: {res.text}")
        except Exception as e:
            logger.debug(f"Telegram notify error: {e}")

    # =========================================================================
    # ТЕМАТИЧЕСКИЕ АЛЕРТЫ
    # =========================================================================

    def notify_order_opened(self, order_data: Dict[str, Any], is_dry_run: bool = True):
        """🟢 Алерт: Вход в сделку."""
        sym = order_data.get("symbol", "N/A")
        side = order_data.get("side", "N/A").upper()
        qty = order_data.get("qty", 0.0)
        price = order_data.get("price", 0.0)
        sl = order_data.get("sl_price", 0.0)
        tp = order_data.get("tp_price", 0.0)
        net_rr = order_data.get("net_rr", 0.0)
        tag = "🧪 [СИМУЛЯЦИЯ]" if is_dry_run else "⚡ [БОЕВОЙ ОРДЕР]"

        side_icon = "🟢 LONG (BUY)" if side in ("BUY", "BUY") else "🔴 SHORT (SELL)"
        text = (
            f"<b>{tag} {side_icon}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Монета:</b> <code>{sym}</code>\n"
            f"💵 <b>Вход:</b> <code>${price:,.4f}</code>\n"
            f"📦 <b>Объем:</b> <code>{qty} {sym.replace('USDT','')}</code>\n"
            f"🛑 <b>Stop-Loss:</b> <code>${sl:,.4f}</code>\n"
            f"🎯 <b>Take-Profit:</b> <code>${tp:,.4f}</code>\n"
            f"⚖️ <b>Чистый R:R:</b> <code>{net_rr:.2f}</code>\n"
            f"⏱ <b>Время:</b> <i>{threading.current_thread().name}</i>"
        )
        self.send_message(text)

    def notify_breakeven(self, symbol: str, side: str, new_sl: float, pnl_pct: float, is_dry_run: bool = True):
        """🔵 Алерт: Стоп перенесен в безубыток (+2%)."""
        tag = "[СИМУЛЯЦИЯ]" if is_dry_run else "[РЕАЛ]"
        text = (
            f"🔵 <b>{tag} СТОП ПЕРЕНЕСЕН В БЕЗУБЫТОК</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Монета:</b> <code>{symbol}</code> ({side})\n"
            f"📈 <b>Текущий PnL:</b> <code>+{pnl_pct:.2f}%</code>\n"
            f"🛡 <b>Новый Stop-Loss:</b> <code>${new_sl:,.4f}</code> (Entry + 0.1% комиссия)\n"
            f"✅ <i>Позиция теперь на 100% защищена от убытка!</i>"
        )
        self.send_message(text)

    def notify_trailing(self, symbol: str, side: str, new_sl: float, pnl_pct: float, is_dry_run: bool = True):
        """🚀 Алерт: Trailing Stop подтянут выше (+3.5%+)."""
        tag = "[СИМУЛЯЦИЯ]" if is_dry_run else "[РЕАЛ]"
        text = (
            f"🚀 <b>{tag} TRAILING STOP ПОДТЯНУТ</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Монета:</b> <code>{symbol}</code> ({side})\n"
            f"🔥 <b>Прибыль на пампе:</b> <code>+{pnl_pct:.2f}%</code>\n"
            f"🎯 <b>Защитный Trail Стоп:</b> <code>${new_sl:,.4f}</code>\n"
            f"💰 <i>Прибыль зафиксирована, сделка следует за трендом.</i>"
        )
        self.send_message(text)

    def notify_order_closed(self, symbol: str, reason: str, pnl_usd: float = 0.0, pnl_pct: float = 0.0, is_dry_run: bool = True):
        """🔴 Алерт: Позиция закрыта."""
        tag = "[СИМУЛЯЦИЯ]" if is_dry_run else "[РЕАЛ]"
        icon = "🟢" if pnl_usd >= 0 else "🔴"
        text = (
            f"{icon} <b>{tag} ПОЗИЦИЯ ЗАКРЫТА</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Монета:</b> <code>{symbol}</code>\n"
            f"📌 <b>Причина:</b> <code>{reason}</code>\n"
            f"💵 <b>Результат:</b> <code>${pnl_usd:+,.2f} ({pnl_pct:+,.2f}%)</code>"
        )
        self.send_message(text)

    def notify_catalyst(self, title: str, symbol: Optional[str], impact_score: int, event_type: str, sentiment: str):
        """⚡ Алерт: Обнаружен высокоприоритетный катализатор."""
        if impact_score < 7:
            return
        text = (
            f"⚡ <b>ГОРЯЧИЙ НОВОСТНОЙ КАТАЛИЗАТОР</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Актив:</b> <code>{symbol or 'MARKET'}</code>\n"
            f"💥 <b>Важность:</b> <code>{impact_score}/10</code> ({event_type})\n"
            f"🧭 <b>Тональность:</b> <code>{sentiment}</code>\n"
            f"📰 <b>Заголовок:</b> <i>{title}</i>\n"
            f"🤖 <i>Запущен StateGraph анализ и валидация точки входа...</i>"
        )
        self.send_message(text)

    def notify_emergency_stop(self, closed_count: int, cancelled_count: int):
        """🚨 Алерт: Аварийный стоп (Kill Switch)."""
        text = (
            f"🚨 <b>АВАРИЙНЫЙ РУБИЛЬНИК АКТИВИРОВАН!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🛑 <b>Статус:</b> ВСЯ ТОРГОВЛЯ ОСТАНОВЛЕНА\n"
            f"🔒 <b>Закрыто открытых позиций:</b> <code>{closed_count}</code>\n"
            f"🗑 <b>Отменено лимитных ордеров:</b> <code>{cancelled_count}</code>\n"
            f"⚠️ <i>Для возобновления работы отправьте /resume</i>"
        )
        self.send_message(text)

_notifier_instance: Optional[TelegramNotifier] = None

def get_telegram_notifier() -> TelegramNotifier:
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = TelegramNotifier()
    return _notifier_instance
