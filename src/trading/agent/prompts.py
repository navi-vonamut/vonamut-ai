"""
System and analytical prompts for Fast (gemini-3.5-flash-lite) and Deep (gemma-4-31b-it) trading analysis.
"""

SYSTEM_TRADING_PROMPT = """You are an elite quantitative crypto trading intelligence agent specialized in Bybit Perpetual & Spot markets.
Your goal is to evaluate market structure, orderbook liquidity imbalance, technical indicators, and 24-hour news context to produce an objective, high-probability trading decision.

### CORE PRINCIPLES & RISK RULES:
1. **Capital Preservation First**: Never recommend low-conviction or counter-trend gambling. When in doubt or when indicators conflict, output "HOLD".
2. **Mandatory Risk Management**:
   - Every BUY or SELL action MUST specify an exact `stop_loss`, `take_profit_1`, and `take_profit_2`.
   - The Risk/Reward Ratio (R:R) MUST be at least 1.8:1 (ideally >= 2.0:1).
   - Stop-Loss should be logically placed below recent key support/swing low (for BUY) or above resistance/swing high (for SELL), considering ATR volatility.
3. **Data Integration**:
   - Synthesize Technical Indicators (EMA alignment, RSI momentum/divergence, MACD histogram, Bollinger Bands).
   - Incorporate Real-time Orderbook Dynamics (Orderbook Imbalance ratio, buyer vs seller pressure).
   - Cross-reference with 24h News & Macro Sentiment from Qdrant RAG.
4. **Bilingual Rationale**:
   - Provide comprehensive analysis in `reasoning_en` (English).
   - Also provide clear localized analysis in `reasoning_ru` (Russian).

You MUST output your response matching the structured schema.
"""

def format_analysis_user_prompt(
    symbol: str,
    timeframe: str,
    technical_data: dict,
    news_context_text: str,
    orderbook_data: dict,
    mode: str = "hybrid"
) -> str:
    """Форматирование пользовательского промпта с текущими данными рынка."""
    current_p = technical_data.get("current_price", 0.0)
    trend = technical_data.get("trend", "UNKNOWN")
    ema = technical_data.get("ema", {})
    rsi = technical_data.get("rsi", {})
    macd = technical_data.get("macd", {})
    bb = technical_data.get("bollinger_bands", {})
    atr = technical_data.get("atr", 0.0)
    sup = technical_data.get("support_level", 0.0)
    res = technical_data.get("resistance_level", 0.0)
    vol_ratio = technical_data.get("volume_ratio", 1.0)
    ob_imb = technical_data.get("orderbook_imbalance", {})

    prompt = f"""### TRADING ANALYSIS REQUEST ({mode.upper()} MODE)
**Asset:** {symbol}
**Timeframe:** {timeframe}m
**Current Price:** {current_p}

---
### 1. TECHNICAL INDICATORS
- **Trend State:** {trend}
- **Exponential Moving Averages:**
  * EMA(9): {ema.get('ema9')}
  * EMA(21): {ema.get('ema21')}
  * EMA(50): {ema.get('ema50')}
  * EMA(200): {ema.get('ema200')}
- **RSI (14):** {rsi.get('value')} ({rsi.get('status')})
- **MACD (12, 26, 9):** MACD={macd.get('macd')}, Signal={macd.get('signal')}, Histogram={macd.get('histogram')}
- **Bollinger Bands (20, 2):** Upper={bb.get('upper')}, Middle={bb.get('middle')}, Lower={bb.get('lower')}, BandWidth={bb.get('bandwidth_pct')}%
- **Average True Range (ATR 14):** {atr}
- **Recent Support / Resistance:** Support={sup} | Resistance={res}
- **Volume Ratio (Current / 20-SMA):** {vol_ratio}x

---
### 2. ORDERBOOK MICROSTRUCTURE (L1 REAL-TIME REDIS)
- **Best Bid:** {ob_imb.get('best_bid')} | **Best Ask:** {ob_imb.get('best_ask')} (Spread: {ob_imb.get('spread')})
- **Bid Volume (Top 20):** {ob_imb.get('bid_vol')}
- **Ask Volume (Top 20):** {ob_imb.get('ask_vol')}
- **Imbalance Ratio:** {ob_imb.get('imbalance_ratio')}x -> Sentiment: {ob_imb.get('sentiment')}

---
### 3. NEWS & 24-HOUR RAG CONTEXT (QDRANT)
{news_context_text}

---
### YOUR TASK:
Analyze all data layers above and output a structured decision (BUY, SELL, or HOLD) with exact entry, stop-loss, take-profit levels, risk/reward calculation, and detailed bilingual reasoning.
"""
    return prompt
