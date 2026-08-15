import os
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class SportsConfig(BaseModel):
    odds_api_key: str = Field(default_factory=lambda: os.getenv("ODDS_API_KEY", ""))
    telegram_api_id: int = Field(default_factory=lambda: int(os.getenv("TELEGRAM_API_ID", "0")))
    telegram_api_hash: str = Field(default_factory=lambda: os.getenv("TELEGRAM_API_HASH", ""))
    telegram_phone: str = Field(default_factory=lambda: os.getenv("TELEGRAM_PHONE", ""))
    telegram_session_name: str = Field(default_factory=lambda: os.getenv("TELEGRAM_SESSION_NAME", "sports_insider_session"))
    
    # Спортивные Telegram-каналы инсайдов
    telegram_channels: List[str] = Field(default_factory=lambda: [
        "@sportsru",
        "@nobel_insider",
        "@rpl_insides",
        "@khl_inside"
    ])
    
    qdrant_url: str = Field(default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6335"))
    qdrant_collection_name: str = "sports_context_24h"
    vector_size: int = 3072  # Совместимость с gemini-embedding-2
    embedding_model: str = "models/gemini-embedding-2"
    google_api_key: str = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    
    # Порог валуя (например, 0.05 = перевес > 5%)
    value_threshold: float = 0.05
    target_bookmaker: str = "pinnacle"
    
    target_leagues: List[str] = Field(default_factory=lambda: [
        "soccer_russia_premier_league",
        "soccer_epl",
        "soccer_uefa_champs_league",
        "icehockey_khl",
        "icehockey_nhl"
    ])

    def get_effective_qdrant_url(self) -> str:
        url = self.qdrant_url
        if "qdrant:6333" in url and not os.path.exists("/.dockerenv"):
            return "http://localhost:6335"
        return url

sports_config = SportsConfig()
