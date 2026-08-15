from typing import Dict, Any, List, Optional, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

class TradingDecisionSchema(BaseModel):
    """
    Строгая Pydantic схема торгового решения агента.
    """
    action: Literal["BUY", "SELL", "HOLD"] = Field(
        description="Торговое действие: BUY (Long), SELL (Short) или HOLD (вне рынка)"
    )
    confidence: float = Field(
        description="Уверенность в решении от 0.0 до 1.0 (например, 0.85)",
        ge=0.0,
        le=1.0
    )
    entry_price: float = Field(
        description="Рекомендуемая цена входа (рыночная или лимитная)"
    )
    stop_loss: float = Field(
        description="Обязательный уровень Stop-Loss"
    )
    take_profit_1: float = Field(
        description="Первая цель фиксации прибыли (Take-Profit 1)"
    )
    take_profit_2: float = Field(
        description="Вторая расширенная цель прибыли (Take-Profit 2)"
    )
    risk_reward_ratio: float = Field(
        description="Соотношение Прибыль/Риск (R:R), например 2.3"
    )
    recommended_leverage: int = Field(
        default=5,
        description="Рекомендуемое плечо (от 1 до 20)"
    )
    time_horizon: str = Field(
        default="Intraday",
        description="Горизонт сделки: Scalp (5m-15m), Intraday (1h-4h), Swing (1d+)"
    )
    reasoning_en: str = Field(
        description="Mandatory comprehensive rationale and technical/fundamental thesis in English"
    )
    reasoning_ru: Optional[str] = Field(
        default=None,
        description="Детальное обоснование решения и тезисы на русском языке"
    )
    risk_notes_en: str = Field(
        description="Key invalidation criteria and market risk factors in English"
    )
    risk_notes_ru: Optional[str] = Field(
        default=None,
        description="Условия отмены сетапа и факторы риска на русском языке"
    )

class TradingAgentState(TypedDict, total=False):
    """
    Состояние графа LangGraph (StateGraph).
    """
    # Входные параметры
    symbol: str
    timeframe: str
    mode: str # "fast" (gemini-3.5-flash-lite) | "deep" (gemma-4-31b-it) | "hybrid"
    
    # Собранный контекст
    market_context: Dict[str, Any]
    technical_indicators: Dict[str, Any]
    news_rag_context: Dict[str, Any]
    
    # Аналитическое решение
    decision: Dict[str, Any]
    
    # Локализация и системные логи
    localized_notifications: List[Dict[str, Any]]
    logs: List[str]
    error: Optional[str]
