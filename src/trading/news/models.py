import time
import datetime
from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field

class RawNewsItem(BaseModel):
    """Сырая новость из внешнего источника (CryptoPanic, RSS, Telegram)."""
    id: str
    title: str
    content: str = ""
    url: str = ""
    source: str = "web"
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    published_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    content_hash: str = ""

class NewsTriageResult(BaseModel):
    """Результат быстрой LLM-сортировки новости (Fast Triage Engine)."""
    symbol: Optional[str] = Field(None, description="Тикер монеты без USDT, например BTC, SOL, ENA")
    is_tradable: bool = Field(..., description="Есть ли конкретный торгуемый крипто-актив")
    impact_score: int = Field(..., ge=1, le=10, description="Степень влияния на цену от 1 до 10")
    sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"] = Field(..., description="Торговая направленность")
    event_type: Literal["LISTING", "EXPLOIT", "PARTNERSHIP", "TOKENOMICS", "REGULATORY", "NOISE"] = Field(
        ..., description="Категория катализатора"
    )
    summary_en: str = Field(..., description="Краткое обоснование влияния на английском")
    summary_ru: str = Field(..., description="Краткое обоснование влияния на русском")

class ProcessedCatalystEvent(BaseModel):
    """Обработанное событие-катализатор, готовое для исполнения или передачи в агент."""
    id: str
    news: RawNewsItem
    triage: NewsTriageResult
    bybit_symbol: Optional[str] = None # Например, ENAUSDT
    is_available_on_bybit: bool = False
    status: Literal["IGNORED", "MONITORED", "UNLISTED", "PENDING_ANALYSIS", "ANALYZED", "EXECUTED", "REJECTED_RISK"] = "MONITORED"
    execution_result: Optional[Dict[str, Any]] = None
    created_at: int = Field(default_factory=lambda: int(time.time()))
