import logging
import datetime
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.trading.agent.config import agent_config, AgentConfig
from src.trading.agent.state import TradingAgentState, TradingDecisionSchema
from src.trading.agent.technical_analysis import TechnicalAnalyzer
from src.trading.agent.localization import get_localization_manager, LocalizationManager
from src.trading.agent.prompts import SYSTEM_TRADING_PROMPT, format_analysis_user_prompt
from src.trading.db import get_trading_db
from src.trading.redis_client import get_trading_redis
from src.trading.rag import get_market_rag_service

logger = logging.getLogger(__name__)

# --- NODE 1: Fetch Market, Orderbook & RAG Context ---
def fetch_context_node(state: TradingAgentState) -> Dict[str, Any]:
    symbol = state.get("symbol", "BTCUSDT")
    timeframe = state.get("timeframe", "15")
    db = get_trading_db()
    redis_client = get_trading_redis()
    rag = get_market_rag_service()
    loc = get_localization_manager()

    logger.info(f"Node 1: Fetching context for {symbol} ({timeframe}m)...")

    # 1. Свечи из PostgreSQL
    klines = db.get_latest_klines(symbol, timeframe, limit=100)
    
    # 2. Стакан из Redis L1 Hot Cache
    orderbook = redis_client.get_orderbook(symbol)

    # 3. Новостной контекст и сентимент из Qdrant RAG
    clean_sym = symbol.replace("USDT", "").replace("PERP", "").upper()
    news_summary = rag.get_sentiment_summary(clean_sym, hours_back=24)
    news_prompt_text = rag.format_context_for_prompt(clean_sym, hours_back=24)

    best_bid, best_ask = redis_client.get_best_bid_ask(symbol)
    if not best_bid and klines:
        best_bid = float(klines[-1].close)
        best_ask = float(klines[-1].close)

    log_msg = loc.get_bilingual_log(
        "CONTEXT_FETCHED",
        klines_count=len(klines),
        best_bid=best_bid,
        best_ask=best_ask,
        news_count=news_summary.get("total_articles", 0)
    )

    return {
        "market_context": {
            "klines": klines,
            "orderbook": orderbook,
            "best_bid": best_bid,
            "best_ask": best_ask,
        },
        "news_rag_context": {
            "summary": news_summary,
            "prompt_text": news_prompt_text,
        },
        "logs": [log_msg["message_en"]],
    }

# --- NODE 2: Technical Analysis ---
def technical_analysis_node(state: TradingAgentState) -> Dict[str, Any]:
    symbol = state.get("symbol", "BTCUSDT")
    market_ctx = state.get("market_context", {})
    klines = market_ctx.get("klines", [])
    orderbook = market_ctx.get("orderbook")
    loc = get_localization_manager()

    logger.info(f"Node 2: Computing technical analysis for {symbol}...")

    tech_results = TechnicalAnalyzer.analyze_full_market(klines, orderbook)

    log_msg = loc.get_bilingual_log(
        "TECH_ANALYSIS_COMPLETE",
        symbol=symbol,
        trend=tech_results.get("trend", "UNKNOWN"),
        rsi=tech_results.get("rsi", {}).get("value", 50),
        macd=tech_results.get("macd", {}).get("macd", 0),
        atr=tech_results.get("atr", 0),
        imbalance=tech_results.get("orderbook_imbalance", {}).get("imbalance_ratio", 1.0)
    )

    existing_logs = state.get("logs", [])
    return {
        "technical_indicators": tech_results,
        "logs": existing_logs + [log_msg["message_en"]],
    }

# --- NODE 3: Gemini / Gemma Decision Engine ---
def gemini_decision_node(state: TradingAgentState) -> Dict[str, Any]:
    symbol = state.get("symbol", "BTCUSDT")
    timeframe = state.get("timeframe", "15")
    mode = state.get("mode", agent_config.default_mode)
    tech_data = state.get("technical_indicators", {})
    news_ctx = state.get("news_rag_context", {})
    orderbook_data = state.get("market_context", {}).get("orderbook", {})

    logger.info(f"Node 3: Running LLM decision engine (Mode: {mode})...")

    # Выбор модели:
    # fast -> gemini-3.5-flash-lite
    # deep -> gemma-4-31b-it (с фолбеком на gemini-2.5-flash / gemini-1.5-pro)
    if mode == "deep":
        primary_model = agent_config.deep_model
    else:
        primary_model = agent_config.fast_model

    user_prompt = format_analysis_user_prompt(
        symbol=symbol,
        timeframe=timeframe,
        technical_data=tech_data,
        news_context_text=news_ctx.get("prompt_text", ""),
        orderbook_data=orderbook_data or {},
        mode=mode
    )

    models_to_try = [primary_model, "gemini-2.5-flash", "gemini-1.5-flash"]
    decision_obj: Optional[TradingDecisionSchema] = None
    last_err = None

    for model_name in models_to_try:
        try:
            logger.info(f"Attempting decision with model: {model_name}...")
            llm = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=agent_config.google_api_key if agent_config.google_api_key else None,
                temperature=0.2,
            )
            structured_llm = llm.with_structured_output(TradingDecisionSchema)
            decision_obj = structured_llm.invoke([
                SystemMessage(content=SYSTEM_TRADING_PROMPT),
                HumanMessage(content=user_prompt)
            ])
            if decision_obj:
                break
        except Exception as e:
            last_err = e
            logger.warning(f"Model {model_name} failed: {e}. Trying next fallback...")

    # Фолбек на безопасное решение HOLD при сбое всех моделей
    if not decision_obj:
        logger.error(f"All LLM models failed in decision node: {last_err}")
        current_p = tech_data.get("current_price", 0.0)
        decision_obj = TradingDecisionSchema(
            action="HOLD",
            confidence=0.5,
            entry_price=current_p,
            stop_loss=current_p * 0.98,
            take_profit_1=current_p * 1.02,
            take_profit_2=current_p * 1.04,
            risk_reward_ratio=1.0,
            recommended_leverage=1,
            time_horizon="None",
            reasoning_en=f"Automated risk safety fallback due to model unavailability ({last_err}).",
            reasoning_ru="Автоматический защитный переход в режим HOLD из-за временной недоступности модели.",
            risk_notes_en="Do not open new positions until model connectivity is verified.",
            risk_notes_ru="Не открывать новые позиции до подтверждения связи с моделью."
        )

    decision_dict = decision_obj.model_dump()
    decision_dict["symbol"] = symbol
    existing_logs = state.get("logs", [])
    return {
        "decision": decision_dict,
        "logs": existing_logs + [f"LLM Decision generated for {symbol}: {decision_dict['action']} (Confidence: {decision_dict['confidence']})"],
    }

# --- NODE 4: Localization & Database Logging ---
def localization_logging_node(state: TradingAgentState) -> Dict[str, Any]:
    symbol = state.get("symbol", "BTCUSDT")
    timeframe = state.get("timeframe", "15")
    decision = state.get("decision", {})
    db = get_trading_db()
    loc = get_localization_manager()

    action = decision.get("action", "HOLD")
    entry_p = decision.get("entry_price", 0.0)
    sl = decision.get("stop_loss", 0.0)
    tp1 = decision.get("take_profit_1", 0.0)
    tp2 = decision.get("take_profit_2", 0.0)
    rr = decision.get("risk_reward_ratio", 0.0)
    conf_pct = int(decision.get("confidence", 0.0) * 100)

    # Генерация двуязычного уведомления с гарантированным fallback
    if action == "BUY":
        tpl_key = "SIGNAL_BUY"
    elif action == "SELL":
        tpl_key = "SIGNAL_SELL"
    else:
        tpl_key = "SIGNAL_HOLD"

    bilingual_notif = loc.get_bilingual_log(
        tpl_key,
        symbol=symbol,
        entry_price=entry_p,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        rr=rr,
        confidence=conf_pct,
        trend=state.get("technical_indicators", {}).get("trend", "NEUTRAL"),
        reason=decision.get("reasoning_en", "")[:80]
    )

    # Сохранение лога в PostgreSQL
    db.log_event(
        component="TradingStateGraph",
        message_en=bilingual_notif["message_en"],
        message_ru=bilingual_notif["message_ru"],
        level="INFO" if action == "HOLD" else "SIGNAL_ALERT",
        details={
            "symbol": symbol,
            "timeframe": timeframe,
            "decision": decision,
            "indicators_summary": {
                "trend": state.get("technical_indicators", {}).get("trend"),
                "rsi": state.get("technical_indicators", {}).get("rsi", {}).get("value"),
                "imbalance": state.get("technical_indicators", {}).get("orderbook_imbalance", {}).get("imbalance_ratio")
            }
        }
    )

    existing_logs = state.get("logs", [])
    return {
        "localized_notifications": [bilingual_notif],
        "logs": existing_logs + [bilingual_notif["message_en"]],
    }

def create_trading_agent_graph():
    """
    Построение и компиляция StateGraph агента торговли.
    """
    workflow = StateGraph(TradingAgentState)

    # Добавление узлов
    workflow.add_node("fetch_context", fetch_context_node)
    workflow.add_node("technical_analysis", technical_analysis_node)
    workflow.add_node("gemini_decision", gemini_decision_node)
    workflow.add_node("localization_logging", localization_logging_node)

    # Определение ребер графа
    workflow.set_entry_point("fetch_context")
    workflow.add_edge("fetch_context", "technical_analysis")
    workflow.add_edge("technical_analysis", "gemini_decision")
    workflow.add_edge("gemini_decision", "localization_logging")
    workflow.add_edge("localization_logging", END)

    return workflow.compile()

def run_trading_agent_analysis(
    symbol: str = "BTCUSDT",
    timeframe: str = "15",
    mode: str = "fast"
) -> TradingAgentState:
    """
    Удобная функция запуска полного аналитического цикла агента.
    """
    app = create_trading_agent_graph()
    initial_state: TradingAgentState = {
        "symbol": symbol,
        "timeframe": timeframe,
        "mode": mode,
        "logs": [],
    }
    final_state = app.invoke(initial_state)
    return final_state
