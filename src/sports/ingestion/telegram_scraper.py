import logging
import asyncio
import datetime
from typing import List, Dict, Any, Optional
from src.sports.config import sports_config

logger = logging.getLogger(__name__)

# Попытка импорта Telethon
try:
    from telethon import TelegramClient, events
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logger.warning("[TELEGRAM_SCRAPER] Telethon library is not installed or available.")

class TelegramInsiderScraper:
    """
    Сервис непрерывного сбора текстовых инсайдов из Telegram-каналов с фильтрацией по играющим командам.
    """

    def __init__(self, vectorizer_callback=None):
        self.api_id = sports_config.telegram_api_id
        self.api_hash = sports_config.telegram_api_hash
        self.session_name = sports_config.telegram_session_name
        self.channels = sports_config.telegram_channels
        self.vectorizer_callback = vectorizer_callback
        self.client: Optional[Any] = None
        self._running = False

    async def start(self):
        """Запуск слушателя Telegram-каналов."""
        if not TELETHON_AVAILABLE or not self.api_id or not self.api_hash:
            logger.warning("[TELEGRAM_SCRAPER] Telegram credentials missing or Telethon missing. Running mock listening mode.")
            self._running = True
            asyncio.create_task(self._mock_listening_loop())
            return

        try:
            logger.info(f"[TELEGRAM_SCRAPER] Starting Telethon client for channels: {self.channels}")
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.start(phone=sports_config.telegram_phone)

            @self.client.on(events.NewMessage(chats=self.channels))
            async def event_handler(event):
                text = event.raw_text
                channel_name = getattr(event.chat, 'username', 'unknown_channel')
                if text:
                    await self._process_post(text, channel_name)

            self._running = True
            logger.info("[TELEGRAM_SCRAPER] Telethon listener successfully started.")
            await self.client.run_until_disconnected()
        except Exception as e:
            logger.error(f"[TELEGRAM_SCRAPER] Error in Telethon listener: {e}")
            self._running = True
            asyncio.create_task(self._mock_listening_loop())

    async def _process_post(self, text: str, source_channel: str):
        """Обработка входящего поста из Telegram."""
        post_data = {
            "text": text,
            "source": source_channel,
            "timestamp": int(datetime.datetime.utcnow().timestamp()),
            "timestamp_dt": datetime.datetime.utcnow().isoformat()
        }
        logger.info(f"[TELEGRAM_SCRAPER] Received post from {source_channel}: {text[:60]}...")
        if self.vectorizer_callback:
            try:
                await self.vectorizer_callback(post_data)
            except Exception as e:
                logger.error(f"[TELEGRAM_SCRAPER] Error passing post to vectorizer: {e}")

    async def _mock_listening_loop(self):
        """Фоновый генератор демо-инсайдов для проверки RAG при отсутствии API ключей."""
        logger.info("[TELEGRAM_SCRAPER] Mock insider loop initialized.")
        demo_posts = [
            {
                "text": "СРОЧНО: У Динамо Москва травмировался основной вратарь на тренировке. В стартовом составе выйдет 19-летний дублер. В раздевалке напряженная обстановка из-за недавних ссор с тренером.",
                "source": "@nobel_insider",
                "team1": "Спартак Москва",
                "team2": "Динамо Москва"
            },
            {
                "text": "ИНСАЙД: Спартак Москва выходит в сильнейшем составе. Лидеры атаки полностью восстановились от микротравм. Мотивация максимальная перед дерби.",
                "source": "@rpl_insides",
                "team1": "Спартак Москва",
                "team2": "Динамо Москва"
            }
        ]

        while self._running:
            await asyncio.sleep(300) # каждые 5 минут в демо-режиме
            for post in demo_posts:
                post["timestamp"] = int(datetime.datetime.utcnow().timestamp())
                post["timestamp_dt"] = datetime.datetime.utcnow().isoformat()
                if self.vectorizer_callback:
                    try:
                        await self.vectorizer_callback(post)
                    except Exception as e:
                        logger.error(f"[TELEGRAM_SCRAPER] Mock vectorization error: {e}")

    def stop(self):
        self._running = False
