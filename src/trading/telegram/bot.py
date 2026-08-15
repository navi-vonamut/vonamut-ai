import os
import asyncio
import logging
import threading
from typing import Optional, List, Dict, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.trading.config import trading_config
from src.trading.execution.config import risk_config
from src.trading.telegram.config import telegram_config, TelegramConfig
from src.trading.telegram.notifier import get_telegram_notifier
from src.trading.rest_client import BybitRestClient
from src.trading.execution.order_executor import get_order_executor
from src.trading.redis_client import get_trading_redis
from src.trading.screener import get_screener
from src.trading.news.dispatcher import get_catalyst_dispatcher

logger = logging.getLogger(__name__)

REDIS_EMERGENCY_KEY = "trading:emergency_stop"

class TradingTelegramBot:
    """
    Интерактивный мобильный терминал управления на базе aiogram 3.x.
    Позволяет мониторить баланс, позиции, скринер, новости и мгновенно активировать Kill Switch.
    """

    def __init__(self, config: Optional[TelegramConfig] = None):
        self.config = config or telegram_config
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.redis = get_trading_redis()
        self.executor = get_order_executor()
        self.screener = get_screener()
        self.dispatcher = get_catalyst_dispatcher()
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def is_configured(self) -> bool:
        return bool(self.config.bot_token)

    def _get_main_keyboard(self):
        """Интерактивная клавиатура терминала."""
        builder = InlineKeyboardBuilder()
        builder.button(text="📊 Баланс & Статус", callback_data="cmd_status")
        builder.button(text="🔥 Hot Скринер", callback_data="cmd_screener")
        builder.button(text="💼 Открытые сделки", callback_data="cmd_positions")
        builder.button(text="⚡ Новости-Катализаторы", callback_data="cmd_news")
        builder.button(text="🚨 EMERGENCY STOP", callback_data="cmd_emergency_stop")
        builder.button(text="🔄 Снять стоп (Resume)", callback_data="cmd_resume")
        builder.adjust(2, 2, 2)
        return builder.as_markup()

    async def _cmd_start(self, message: types.Message):
        """Команда /start."""
        mode = "🧪 СИМУЛЯЦИЯ (DRY-RUN)" if risk_config.dry_run else "⚡ РЕАЛЬНАЯ ТОРГОВЛЯ"
        text = (
            f"👋 <b>Добро пожаловать в автономный терминал Vonamut AI!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕹 <b>Режим:</b> <code>{mode}</code>\n"
            f"🤖 <b>Архитектура:</b> <code>News-First Catalyst Engine</code>\n"
            f"🛡 <b>Защита:</b> Trailing Stops + Fee Protection ($R:R \ge 1.8$)\n\n"
            f"Выберите действие в меню ниже или отправьте команду:"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())

    async def _cmd_status(self, target: types.Message | types.CallbackQuery):
        """Команда /status — баланс и состояние 4 контуров."""
        # 1. Баланс
        wallet = self.executor.get_wallet_balance()
        equity = wallet.get("total_equity", 0.0)
        avail = wallet.get("available_margin", 0.0)
        margin_used = wallet.get("total_margin_balance", 0.0)

        # 2. Статус контуров
        redis_ok = "🟢 OK" if self.redis.is_connected() else "🔴 ERROR"
        is_halted = False
        if self.redis.is_connected() and self.redis.client:
            is_halted = bool(self.redis.client.get(REDIS_EMERGENCY_KEY))
        
        emergency_status = "🔴 ОСТАНОВЛЕН (HALTED)" if is_halted else "🟢 АКТИВЕН"
        mode = "🧪 СИМУЛЯЦИЯ (DRY-RUN)" if risk_config.dry_run else "⚡ БОЕВОЙ (LIVE)"

        text = (
            f"📊 <b>СИСТЕМНЫЙ СТАТУС ТЕРМИНАЛА</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>Депозит (Equity):</b> <code>${equity:,.2f} USDT</code>\n"
            f"💳 <b>Свободная маржа:</b> <code>${avail:,.2f} USDT</code>\n"
            f"🔒 <b>Занятая маржа:</b> <code>${margin_used:,.2f} USDT</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕹 <b>Режим исполнения:</b> <code>{mode}</code>\n"
            f"🚨 <b>Торговый статус:</b> <code>{emergency_status}</code>\n"
            f"⚡ <b>Redis Hot Cache:</b> <code>{redis_ok}</code>\n"
            f"🏛 <b>Bybit Unified V5:</b> <code>🟢 ПОДКЛЮЧЕНО</code>\n"
            f"🧠 <b>Gemini 3.5 Flash-Lite:</b> <code>🟢 ГОТОВ</code>\n"
        )
        if isinstance(target, types.CallbackQuery):
            await target.message.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())
            await target.answer()
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())

    async def _cmd_screener(self, target: types.Message | types.CallbackQuery):
        """Команда /screener — топ волатильных монет."""
        hot_pairs = self.screener.get_hot_movers(limit=5)
        if not hot_pairs:
            text = "🔍 <b>Скринер рынка:</b> В данный момент подходящих под фильтры ($V > $20M, |\Delta P| > 5%) монет не обнаружено."
        else:
            text = "🔥 <b>ТОП-5 ГОРЯЧИХ МОНЕТ (BYBIT RADAR)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            for i, p in enumerate(hot_pairs, 1):
                sym = p.get("symbol", "")
                p24 = p.get("price_change_24h_pct", 0.0)
                p1 = p.get("price_change_1h_pct", 0.0)
                vol = p.get("volume_24h_usd", 0.0) / 1_000_000.0
                oi_trend = p.get("oi_trend", "FLAT")
                icon = "🟢" if p24 >= 0 else "🔴"

                text += (
                    f"<b>{i}. {sym}</b> {icon} <code>{p24:+.2f}%</code> (1h: <code>{p1:+.2f}%</code>)\n"
                    f"   ├ Объем 24h: <code>${vol:.1f}M</code>\n"
                    f"   └ Тренд OI: <code>{oi_trend}</code>\n\n"
                )

        if isinstance(target, types.CallbackQuery):
            await target.message.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())
            await target.answer()
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())

    async def _cmd_positions(self, target: types.Message | types.CallbackQuery):
        """Команда /positions — список открытых сделок."""
        positions = self.executor.get_open_positions()
        if not positions:
            text = (
                f"💼 <b>ОТКРЫТЫЕ ПОЗИЦИИ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>В данный момент открытых позиций нет. Маржа на 100% свободна.</i>"
            )
        else:
            text = f"💼 <b>ОТКРЫТЫЕ ПОЗИЦИИ ({len(positions)})</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            for p in positions:
                sym = p.get("symbol", "")
                side = p.get("side", "")
                size = p.get("size", 0.0)
                entry = p.get("entry_price", 0.0)
                mark = p.get("mark_price", 0.0)
                pnl = p.get("unrealised_pnl", 0.0)
                sl = p.get("stop_loss", 0.0)
                tp = p.get("take_profit", 0.0)
                side_icon = "🟢 LONG" if side == "Buy" else "🔴 SHORT"
                pnl_icon = "🟢" if pnl >= 0 else "🔴"

                text += (
                    f"<b>{sym}</b> {side_icon} (x{p.get('leverage', 1):.0f})\n"
                    f"├ Объем: <code>{size}</code> | Вход: <code>${entry:,.4f}</code>\n"
                    f"├ Маркировка: <code>${mark:,.4f}</code>\n"
                    f"├ UnPnL: {pnl_icon} <code>${pnl:+,.2f}</code>\n"
                    f"└ SL: <code>${sl:,.4f}</code> | TP: <code>${tp:,.4f}</code>\n\n"
                )

        if isinstance(target, types.CallbackQuery):
            await target.message.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())
            await target.answer()
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())

    async def _cmd_news(self, target: types.Message | types.CallbackQuery):
        """Команда /news — последние новости-катализаторы."""
        feed = self.dispatcher.get_recent_feed(limit=5)
        if not feed:
            text = "⚡ <b>Новостной радар:</b> Лента катализаторов пока пуста."
        else:
            text = "⚡ <b>ПОСЛЕДНИЕ НОВОСТНЫЕ КАТАЛИЗАТОРЫ</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            for i, ev in enumerate(feed, 1):
                triage = ev.get("triage", {})
                sym = triage.get("symbol") or "MARKET"
                impact = triage.get("impact_score", 1)
                event_type = triage.get("event_type", "NOISE")
                title = ev.get("news", {}).get("title", "")
                status = ev.get("status", "MONITORED")

                impact_icon = "🔥" if impact >= 7 else "⚡"
                text += (
                    f"<b>{i}. {impact_icon} [{sym}] Impact {impact}/10</b> ({event_type})\n"
                    f"├ Статус: <code>{status}</code>\n"
                    f"└ <i>{title[:75]}...</i>\n\n"
                )

        if isinstance(target, types.CallbackQuery):
            await target.message.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())
            await target.answer()
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())

    async def _cmd_emergency_stop(self, target: types.Message | types.CallbackQuery):
        """Аварийный рубильник (Kill Switch) — экстренное закрытие всех позиций."""
        logger.warning("🚨 EMERGENCY STOP INITIATED VIA TELEGRAM!")

        # 1. Флаг останова в Redis
        if self.redis.is_connected() and self.redis.client:
            self.redis.client.set(REDIS_EMERGENCY_KEY, "true")

        # 2. Экстренное закрытие открытых позиций
        open_positions = self.executor.get_open_positions()
        closed_count = 0
        for pos in open_positions:
            sym = pos.get("symbol")
            side = "Sell" if pos.get("side") == "Buy" else "Buy"
            qty = float(pos.get("size", 0.0) or 0.0)
            if sym and qty > 0:
                self.executor.close_position(symbol=sym, side=side, qty=qty)
                closed_count += 1

        text = (
            f"🚨 <b>АВАРИЙНЫЙ РУБИЛЬНИК АКТИВИРОВАН!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛑 <b>Статус:</b> ВСЯ ТОРГОВЛЯ ПРИОСТАНОВЛЕНА\n"
            f"🔒 <b>Закрыто позиций по рынку:</b> <code>{closed_count}</code>\n"
            f"⚠️ <i>Все новые сигналы будут блокироваться Risk Engine.</i>\n\n"
            f"Для возобновления работы нажмите <b>Снять стоп (Resume)</b> или отправьте <code>/resume</code>."
        )

        if isinstance(target, types.CallbackQuery):
            await target.message.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())
            await target.answer()
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())

    async def _cmd_resume(self, target: types.Message | types.CallbackQuery):
        """Снятие аварийного останова."""
        if self.redis.is_connected() and self.redis.client:
            self.redis.client.delete(REDIS_EMERGENCY_KEY)

        text = (
            f"🔄 <b>АВАРИЙНЫЙ РЕЖИМ СНЯТ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 <b>Торговый контур снова АКТИВЕН</b>\n"
            f"🤖 <i>Скринер, News-First анализатор и Risk Engine продолжают работу в штатном режиме.</i>"
        )

        if isinstance(target, types.CallbackQuery):
            await target.message.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())
            await target.answer()
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=self._get_main_keyboard())

    def start_background(self):
        """Запуск Telegram бота в отдельном потоке (asyncio event loop)."""
        if not self.is_configured():
            logger.info("TelegramBot: TELEGRAM_BOT_TOKEN not set. Interactive bot is standby.")
            return

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_bot_thread, name="TelegramBotRunner", daemon=True)
        self._thread.start()
        logger.info("TradingTelegramBot thread started in background.")

    def _run_bot_thread(self):
        """Цикл событий aiogram в отдельном потоке."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._main_async())

    async def _main_async(self):
        self.bot = Bot(token=self.config.bot_token)
        self.dp = Dispatcher()

        # Регистрация команд
        self.dp.message.register(self._cmd_start, Command(commands=["start", "help"]))
        self.dp.message.register(self._cmd_status, Command(commands=["status"]))
        self.dp.message.register(self._cmd_screener, Command(commands=["screener"]))
        self.dp.message.register(self._cmd_positions, Command(commands=["positions"]))
        self.dp.message.register(self._cmd_news, Command(commands=["news"]))
        self.dp.message.register(self._cmd_emergency_stop, Command(commands=["emergency_stop", "halt"]))
        self.dp.message.register(self._cmd_resume, Command(commands=["resume"]))

        # Регистрация callback кнопок
        self.dp.callback_query.register(self._cmd_status, F.data == "cmd_status")
        self.dp.callback_query.register(self._cmd_screener, F.data == "cmd_screener")
        self.dp.callback_query.register(self._cmd_positions, F.data == "cmd_positions")
        self.dp.callback_query.register(self._cmd_news, F.data == "cmd_news")
        self.dp.callback_query.register(self._cmd_emergency_stop, F.data == "cmd_emergency_stop")
        self.dp.callback_query.register(self._cmd_resume, F.data == "cmd_resume")

        logger.info("Starting Telegram Bot long-polling...")
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Telegram Bot polling error: {e}")

_bot_instance: Optional[TradingTelegramBot] = None

def get_telegram_bot() -> TradingTelegramBot:
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = TradingTelegramBot()
    return _bot_instance
