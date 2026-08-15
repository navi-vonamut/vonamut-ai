import os
import logging
import asyncio
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.sports.config import sports_config
from src.db.base import SessionLocal
from src.db.models import SportsBet

logger = logging.getLogger(__name__)

class SportsTelegramBot:
    """
    Telegram-терминал для спортивной аналитики на базе aiogram 3.x.
    """

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self._running = False

    def is_configured(self) -> bool:
        return bool(self.bot_token) and bool(self.chat_id)

    async def init_bot(self):
        if not self.is_configured():
            logger.warning("[SPORTS_BOT] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")
            return

        self.bot = Bot(token=self.bot_token)
        self.dp = Dispatcher()

        # Регистрация обработчиков
        self.dp.message.register(self._cmd_start, Command("sports"))
        self.dp.callback_query.register(self._handle_bet_callback, F.data.startswith("sports_bet_"))

    async def start_background(self):
        """Запуск слушателя бота в фоновой задаче."""
        if not self.is_configured():
            return
        await self.init_bot()
        self._running = True
        logger.info("[SPORTS_BOT] Starting aiogram sports bot polling...")
        asyncio.create_task(self.dp.start_polling(self.bot))

    async def send_value_bet_signal(self, bet_data: Dict[str, Any]) -> bool:
        """
        Отправка структурированного уведомления о найденном валуе.
        """
        if not self.bot or not self.chat_id:
            logger.warning("[SPORTS_BOT] Bot not initialized or chat_id missing. Signal not sent via Telegram.")
            return False

        bet_id = bet_data.get("bet_record_id", 0)
        team1 = bet_data.get("team1", "Команда А")
        team2 = bet_data.get("team2", "Команда Б")
        bet_target = bet_data.get("best_outcome", "Победа 1")
        odds = bet_data.get("selected_odds", 2.0)
        ai_prob = bet_data.get("selected_prob", 0.5) * 100
        value_pct = bet_data.get("value_percentage", 0.05) * 100
        reasoning = bet_data.get("ai_reasoning", "Нет данных.")

        # Форматирование по спецификации Этапа 4
        msg_text = (
            f"🎯 <b>Матч</b>: {team1} — {team2}\n"
            f"📊 <b>Ставка</b>: {bet_target} (Коэф: <b>{odds:.2f}</b>)\n"
            f"🧠 <b>Оценка ИИ</b>: {ai_prob:.0f}% (Value: <b>+{value_pct:.1f}%</b>)\n"
            f"📝 <b>Причина</b>: {reasoning}"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Поставил", callback_data=f"sports_bet_placed_{bet_id}")
        builder.button(text="❌ Скип", callback_data=f"sports_bet_skipped_{bet_id}")
        builder.adjust(2)

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=msg_text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            logger.info(f"[SPORTS_BOT] Sent Value Bet alert for {team1} vs {team2}")
            return True
        except Exception as e:
            logger.error(f"[SPORTS_BOT] Error sending value bet Telegram alert: {e}")
            return False

    async def _cmd_start(self, message: types.Message):
        """Команда /sports для просмотра статистики."""
        db: Session = SessionLocal()
        try:
            placed_count = db.query(SportsBet).filter_by(user_action="PLACED").count()
            skipped_count = db.query(SportsBet).filter_by(user_action="SKIPPED").count()
            pending_count = db.query(SportsBet).filter_by(user_action="PENDING").count()

            text = (
                "🏆 <b>Терминал спортивной аналитики (Value Betting)</b>\n\n"
                f"✅ Оформлено ставок: <b>{placed_count}</b>\n"
                f"❌ Пропущено (Скип): <b>{skipped_count}</b>\n"
                f"⏳ В ожидании ответа: <b>{pending_count}</b>\n\n"
                "<i>Система автоматически присылает сигналы при обнаружении валуя > +5%.</i>"
            )
            await message.answer(text, parse_mode="HTML")
        except Exception as e:
            await message.answer(f"Ошибка получения статистики: {e}")
        finally:
            db.close()

    async def _handle_bet_callback(self, callback: types.CallbackQuery):
        """Обработка клика по кнопкам [ ✅ Поставил ] / [ ❌ Скип ]."""
        data = callback.data # "sports_bet_placed_123" или "sports_bet_skipped_123"
        parts = data.split("_")
        if len(parts) < 4:
            await callback.answer("Ошибка формата данных")
            return

        action = parts[2].upper() # PLACED или SKIPPED
        bet_id = int(parts[3])

        db: Session = SessionLocal()
        try:
            bet_obj = db.query(SportsBet).filter_by(id=bet_id).first()
            if bet_obj:
                bet_obj.user_action = action
                db.commit()
                
                status_label = "✅ ПОСТАВИЛ" if action == "PLACED" else "❌ СКИПНУЛ"
                await callback.answer(f"Статус обновлен: {status_label}")

                # Обновляем сообщение, добавляя метку выбора
                if callback.message and callback.message.text:
                    orig_text = callback.message.text
                    new_text = f"{orig_text}\n\n<b>Решение принята:</b> {status_label}"
                    await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
            else:
                await callback.answer("Запись ставки не найдена", show_alert=True)
        except Exception as e:
            db.rollback()
            logger.error(f"[SPORTS_BOT] Error updating bet status: {e}")
            await callback.answer("Ошибка обновления в БД", show_alert=True)
        finally:
            db.close()

_sports_bot_instance: Optional[SportsTelegramBot] = None

def get_sports_telegram_bot() -> SportsTelegramBot:
    global _sports_bot_instance
    if _sports_bot_instance is None:
        _sports_bot_instance = SportsTelegramBot()
    return _sports_bot_instance
