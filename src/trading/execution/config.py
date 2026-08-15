import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class RiskConfig(BaseModel):
    # Risk Limits
    max_risk_per_trade_pct: float = 1.0       # 1.0% макс. риск депозита на 1 сделку
    max_account_margin_usage_pct: float = 25.0 # Не более 25% депозита в одной позиции
    min_risk_reward_ratio: float = 1.8        # Минимальный коэффициент R:R (1.8 к 1)
    max_open_positions: int = 3               # Максимум 3 открытые позиции одновременно
    max_daily_drawdown_pct: float = 5.0       # Дневной лимит просадки 5%
    max_leverage: int = 10                    # Максимально допустимое плечо
    default_leverage: int = 5                 # Плечо по умолчанию
    min_confidence_to_trade: float = 0.65     # Минимальная уверенность модели для входа

    # Режим исполнения
    # Если dry_run = True, ордера только валидируются и логируются без отправки на биржу
    dry_run: bool = Field(
        default_factory=lambda: os.getenv("TRADING_DRY_RUN", "false").lower() in ("true", "1", "yes")
    )

risk_config = RiskConfig()
