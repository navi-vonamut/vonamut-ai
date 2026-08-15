import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class TelegramConfig(BaseModel):
    """Конфигурация Telegram бота."""
    bot_token: str = Field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    admin_chat_id: str = Field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", os.getenv("TELEGRAM_ADMIN_ID", "")))
    alerts_enabled: bool = Field(default_factory=lambda: os.getenv("TELEGRAM_ALERTS_ENABLED", "true").lower() in ("true", "1", "yes"))

telegram_config = TelegramConfig()
