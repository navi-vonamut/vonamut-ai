import os
from pydantic import BaseModel, Field

class ScreenerConfig(BaseModel):
    """Конфигурация параметров фильтрации и сканирования рынка Bybit."""
    min_24h_turnover_usd: float = Field(
        default=20_000_000.0,
        description="Минимальный суточный объем торгов (USD) для отсева неликвидных пар"
    )
    min_24h_change_pct: float = Field(
        default=5.0,
        description="Минимальное абсолютное изменение цены за 24ч (%)"
    )
    min_1h_change_pct: float = Field(
        default=2.0,
        description="Минимальное абсолютное изменение цены за 1ч (%)"
    )
    check_oi_growth: bool = Field(
        default=True,
        description="Проверять рост открытого интереса (Open Interest)"
    )
    scan_interval_sec: int = Field(
        default=300,
        description="Интервал фонового сканирования рынка (5 минут)"
    )
    top_limit: int = Field(
        default=10,
        description="Максимальное количество горячих пар в топе"
    )
    category: str = Field(
        default="linear",
        description="Категория деривативов Bybit"
    )

screener_config = ScreenerConfig(
    min_24h_turnover_usd=float(os.getenv("SCREENER_MIN_VOLUME_USD", "20000000.0")),
    min_24h_change_pct=float(os.getenv("SCREENER_MIN_24H_CHANGE", "5.0")),
    min_1h_change_pct=float(os.getenv("SCREENER_MIN_1H_CHANGE", "2.0")),
    scan_interval_sec=int(os.getenv("SCREENER_INTERVAL_SEC", "300")),
    top_limit=int(os.getenv("SCREENER_TOP_LIMIT", "10")),
)
