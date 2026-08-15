import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class AgentConfig(BaseModel):
    # LLM Models
    # Быстрые решения и скальпинг
    fast_model: str = Field(default_factory=lambda: os.getenv("TRADING_FAST_MODEL", "gemini-3.5-flash-lite"))
    # Глубокий анализ и рассуждение
    deep_model: str = Field(default_factory=lambda: os.getenv("TRADING_DEEP_MODEL", "gemma-4-31b-it"))

    google_api_key: str = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    
    # Режим принятия решений: "fast" | "deep" | "hybrid"
    default_mode: str = "hybrid"

    # Параметры риск-менеджмента по умолчанию для подсказок модели
    max_risk_per_trade_pct: float = 1.5 # 1.5% макс риск на сделку
    min_risk_reward_ratio: float = 1.8  # Мин соотношение прибыль/риск 1.8:1
    default_leverage: int = 5

agent_config = AgentConfig()
