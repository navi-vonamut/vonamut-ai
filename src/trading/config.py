import os
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class TradingConfig(BaseModel):
    # Bybit Credentials
    api_key: str = Field(default_factory=lambda: os.getenv("BYBIT_API_KEY", ""))
    api_secret: str = Field(default_factory=lambda: os.getenv("BYBIT_API_SECRET", ""))
    demo: bool = Field(default_factory=lambda: os.getenv("BYBIT_DEMO", "true").lower() in ("true", "1", "yes"))
    testnet: bool = Field(default=False)
    dry_run: bool = Field(default_factory=lambda: os.getenv("TRADING_DRY_RUN", "false").lower() in ("true", "1", "yes"))
    category: str = "linear" # linear (USDT Perpetual), spot, inverse

    # Monitored Symbols & Intervals
    symbols: List[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    kline_intervals: List[str] = Field(default_factory=lambda: ["1", "5", "15", "60", "D"])

    # Ingestion Buffer & Batch Settings
    ws_buffer_max_size: int = 10000
    db_batch_size: int = 100
    db_flush_interval_sec: float = 1.0
    orderbook_depth: int = 50

    # Database
    db_url: str = Field(
        default_factory=lambda: os.getenv(
            "ASTRO_DB_URL",
            os.getenv("DATABASE_URL", "postgresql://astro_user:astro_password@postgres:5432/astroguido_db")
        )
    )

    # Redis Hot Cache
    redis_url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://redis:6379/0")
    )

    def get_effective_db_url(self) -> str:
        url = self.db_url
        if "@postgres:" in url and not os.path.exists("/.dockerenv"):
            url = url.replace("@postgres:5432", "@localhost:5433").replace("@postgres", "@localhost:5433")
        return url

    def get_effective_redis_url(self) -> str:
        url = self.redis_url
        if "redis://redis:" in url and not os.path.exists("/.dockerenv"):
            url = url.replace("redis://redis:6379", "redis://localhost:6380").replace("redis://redis", "redis://localhost:6380")
        return url

trading_config = TradingConfig()
