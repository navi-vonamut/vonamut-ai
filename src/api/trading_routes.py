import os
import time
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Body, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from src.trading.config import trading_config
from src.trading.db import get_trading_db
from src.trading.redis_client import get_trading_redis
from src.trading.rest_client import BybitRestClient
from src.trading.rag import get_market_rag_service, get_qdrant_news_manager
from src.trading.agent import run_trading_agent_analysis, agent_config
from src.trading.execution import get_execution_service, get_order_executor, risk_config
from src.trading.models import MarketKline, TradingSystemLog
from src.trading.execution.models import TradingOrder

logger = logging.getLogger("TradingAPI")
router = APIRouter(prefix="/api/trading", tags=["Trading Agent"])

# --- WebSocket Connection Manager ---
class TradingWSConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Active: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)

ws_manager = TradingWSConnectionManager()

# --- Request Models ---
class AnalyzeRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT", description="Торговая пара (например, BTCUSDT)")
    timeframe: str = Field(default="15", description="Интервал свечи: 1, 5, 15, 60, D")
    mode: str = Field(default="fast", description="Режим анализа: fast (gemini-3.5-flash-lite) или deep (gemma-4-31b-it)")

class ExecuteRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT")
    timeframe: str = Field(default="15")
    mode: str = Field(default="fast")
    live: bool = Field(default=False, description="True для отправки реального ордера на биржу, False для Dry-Run симуляции")

class ClosePositionRequest(BaseModel):
    symbol: str = Field(..., description="Символ монеты для закрытия позиции")

# --- REST Endpoints ---

@router.get("/status")
async def get_system_status():
    """
    Проверка состояния 4 контуров торговой системы:
    1. Database (PostgreSQL)
    2. Qdrant (Vector DB)
    3. Bybit API (V5 REST & WS)
    4. Gemini / Gemma AI (Google GenAI)
    """
    statuses = {}

    # 1. PostgreSQL
    try:
        from sqlalchemy import text
        t0 = time.time()
        db = get_trading_db()
        with db.get_session() as s:
            s.execute(text("SELECT 1"))
        latency_pg = round((time.time() - t0) * 1000, 1)
        statuses["database"] = {
            "status": "online",
            "name": "PostgreSQL 15",
            "latency_ms": latency_pg,
            "details": f"Connected to {db.db_url.split('@')[-1]}"
        }
    except Exception as e:
        statuses["database"] = {"status": "offline", "name": "PostgreSQL 15", "error": str(e)}

    # 2. Qdrant Vector Store
    try:
        t0 = time.time()
        qdrant = get_qdrant_news_manager()
        is_conn = qdrant.check_connection()
        latency_qd = round((time.time() - t0) * 1000, 1)
        statuses["qdrant"] = {
            "status": "online" if is_conn else "offline",
            "name": "Qdrant Vector DB",
            "latency_ms": latency_qd,
            "collection": qdrant.config.collection_name,
            "embedding_model": qdrant.config.embedding_model,
            "dimension": qdrant.config.vector_size
        }
    except Exception as e:
        statuses["qdrant"] = {"status": "offline", "name": "Qdrant Vector DB", "error": str(e)}

    # 3. Bybit API V5
    try:
        t0 = time.time()
        client = BybitRestClient()
        res = client.check_connection()
        latency_bybit = round((time.time() - t0) * 1000, 1)
        statuses["bybit"] = {
            "status": "online" if res.get("status") == "connected" else "offline",
            "name": "Bybit Unified V5",
            "latency_ms": latency_bybit,
            "demo": trading_config.demo,
            "server_time_ms": res.get("server_time_ms")
        }
    except Exception as e:
        statuses["bybit"] = {"status": "offline", "name": "Bybit Unified V5", "error": str(e)}

    # 4. Gemini / Gemma AI
    try:
        statuses["gemini_ai"] = {
            "status": "online" if agent_config.google_api_key else "warning",
            "name": "Google Gemini & Gemma",
            "fast_model": agent_config.fast_model,
            "deep_model": agent_config.deep_model,
            "has_api_key": bool(agent_config.google_api_key)
        }
    except Exception as e:
        statuses["gemini_ai"] = {"status": "offline", "name": "Google GenAI", "error": str(e)}

    # 5. Redis L1 Cache
    try:
        redis_client = get_trading_redis()
        redis_ok = redis_client.ping()
        statuses["redis"] = {
            "status": "online" if redis_ok else "offline",
            "name": "Redis 7 (L1 Hot Cache)",
        }
    except Exception as e:
        statuses["redis"] = {"status": "offline", "name": "Redis 7", "error": str(e)}

    return {
        "timestamp": int(time.time()),
        "all_healthy": all(s.get("status") == "online" for s in statuses.values()),
        "circuits": statuses
    }

@router.get("/wallet")
async def get_wallet():
    """Получение баланса, капитала (Equity) и маржинальных параметров Bybit Unified счета."""
    executor = get_order_executor()
    wallet_info = executor.get_wallet_balance()
    return wallet_info

@router.get("/positions")
async def get_positions():
    """Получение списка активных открытых позиций."""
    executor = get_order_executor()
    positions = executor.get_open_positions()
    return {"positions": positions, "total_open": len(positions)}

@router.post("/positions/close")
async def close_position(req: ClosePositionRequest):
    """Закрытие открытой позиции по монете."""
    executor = get_order_executor()
    positions = executor.get_open_positions(symbol=req.symbol)
    if not positions:
        raise HTTPException(status_code=404, detail=f"No active open position found for {req.symbol}")

    pos = positions[0]
    side_to_close = "Sell" if pos["side"] == "Buy" else "Buy"
    
    res = executor.place_order_with_tpsl(
        symbol=req.symbol,
        side=side_to_close,
        qty=pos["size"],
        order_type="Market"
    )

    # Broadcast event
    await ws_manager.broadcast({
        "type": "POSITION_CLOSED",
        "symbol": req.symbol,
        "size": pos["size"],
        "result": res
    })

    return {"status": "success", "closed_position": pos, "order_result": res}

@router.post("/emergency-stop")
async def emergency_stop():
    """
    🚨 EMERGENCY STOP:
    1. Получает все открытые позиции и отправляет встречные рыночные ордера для их немедленного закрытия.
    2. Логирует критическое событие в PostgreSQL.
    """
    logger.warning("🚨 EMERGENCY STOP TRIGGERED VIA API/UI!")
    executor = get_order_executor()
    db = get_trading_db()
    
    positions = executor.get_open_positions()
    closed_results = []
    
    for pos in positions:
        sym = pos["symbol"]
        close_side = "Sell" if pos["side"] == "Buy" else "Buy"
        order_res = executor.place_order_with_tpsl(
            symbol=sym,
            side=close_side,
            qty=pos["size"],
            order_type="Market"
        )
        closed_results.append({"symbol": sym, "side": close_side, "size": pos["size"], "res": order_res})

    db.log_event(
        component="EmergencyStop",
        message_en=f"🚨 EMERGENCY STOP ACTIVATED: Closed {len(closed_results)} positions.",
        message_ru=f"🚨 АВАРИЙНАЯ ОСТАНОВКА АКТИВИРОВАНА: Закрыто {len(closed_results)} позиций.",
        level="CRITICAL",
        details={"closed_positions": closed_results}
    )

    await ws_manager.broadcast({
        "type": "EMERGENCY_STOP_ACTIVATED",
        "closed_count": len(closed_results),
        "details": closed_results
    })

    return {
        "status": "EMERGENCY_STOP_EXECUTED",
        "closed_positions_count": len(closed_results),
        "details": closed_results
    }

@router.get("/fee-rate")
async def get_fee_rate_endpoint(
    symbol: str = Query("BTCUSDT"),
    category: str = Query("linear")
):
    """Получение актуальных комиссий для аккаунта и монеты через GET /v5/account/fee-rate."""
    from src.trading.execution.order_executor import BybitOrderExecutor
    executor = BybitOrderExecutor()
    rates = executor.get_fee_rate(symbol=symbol, category=category)
    return rates

@router.get("/screener")
async def get_screener_results():
    """Получение горячих пар и результатов сканера рынка Bybit."""
    from src.trading.screener import get_screener_worker
    worker = get_screener_worker()
    cached = worker.get_cached_snapshot()
    if cached:
        return cached
    # Если кэш пуст, выполняем сканирование
    snapshot = worker.run_scan_and_cache()
    return snapshot.model_dump()

@router.post("/screener/scan")
async def trigger_screener_scan():
    """Принудительный запуск сканирования рынка Bybit."""
    from src.trading.screener import get_screener_worker
    worker = get_screener_worker()
    snapshot = worker.run_scan_and_cache()
    return {
        "status": "SCAN_COMPLETED",
        "snapshot": snapshot.model_dump()
    }

@router.get("/news")
async def get_news_context(
    symbol: str = Query("BTCUSDT"),
    hours_back: int = Query(24, ge=1, le=168)
):
    """Получение новостного фона, катализаторов и сентимента из векторной БД Qdrant (3072d)."""
    from src.trading.rag import get_market_rag_service
    rag = get_market_rag_service()
    clean_sym = symbol.replace("USDT", "").replace("PERP", "").upper()
    summary = rag.get_sentiment_summary(clean_sym, hours_back=hours_back)
    articles = rag.query_24h_context(clean_sym, hours_back=hours_back, limit=10)
    return {
        "symbol": symbol,
        "clean_symbol": clean_sym,
        "summary": summary,
        "articles": articles
    }

@router.post("/news/sync")
async def sync_news_endpoint(
    symbol: Optional[str] = Query(None)
):
    """Синхронизация и векторизация свежих новостей через CryptoPanic / Tavily в Qdrant."""
    from src.trading.rag import get_market_rag_service
    rag = get_market_rag_service()
    if symbol:
        clean_sym = symbol.replace("USDT", "").replace("PERP", "").upper()
        res = rag.sync_hot_movers_news([clean_sym])
    else:
        res = rag.sync_news()
    return {
        "status": "NEWS_SYNCED",
        "details": res
    }

@router.get("/news/feed")
async def get_catalyst_feed(limit: int = Query(20, ge=1, le=50)):
    """Получение живой ленты обработанных новостей-катализаторов с оценками LLM Triage."""
    from src.trading.news import get_catalyst_dispatcher
    dispatcher = get_catalyst_dispatcher()
    feed = dispatcher.get_recent_feed(limit=limit)
    return {
        "count": len(feed),
        "feed": feed
    }

class ManualTriageRequest(BaseModel):
    title: str
    content: Optional[str] = ""
    url: Optional[str] = ""
    source: Optional[str] = "manual"

@router.post("/news/triage")
async def manual_news_triage(req: ManualTriageRequest):
    """Ручная экспресс-сортировка новости через Fast LLM Triage Engine."""
    import hashlib
    from src.trading.news import RawNewsItem, get_catalyst_dispatcher
    chash = hashlib.md5(f"{req.url}|{req.title}".encode()).hexdigest()
    item = RawNewsItem(
        id=chash,
        title=req.title,
        content=req.content or "",
        url=req.url or "",
        source=req.source or "manual",
        content_hash=chash
    )
    dispatcher = get_catalyst_dispatcher()
    event = dispatcher.process_incoming_news(item)
    return event.model_dump()

@router.post("/news/poll-now")
async def poll_news_firehose_now():
    """Принудительный немедленный опрос потока новостей."""
    from src.trading.news import get_news_stream_listener
    listener = get_news_stream_listener()
    new_items = listener.poll_new_articles()
    return {
        "status": "POLL_COMPLETED",
        "new_articles_count": len(new_items),
        "articles": [x.model_dump() for x in new_items]
    }

@router.get("/klines")
async def get_klines(
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("15"),
    limit: int = Query(100, ge=10, le=500)
):
    """Получение свечей для построения графиков из PostgreSQL или REST."""
    db = get_trading_db()
    # 1. Always fetch fresh klines from Bybit REST API
    try:
        client = BybitRestClient()
        raw_klines = client.get_kline(symbol=symbol, interval=interval, limit=limit)
        if raw_klines:
            db.upsert_klines_batch(raw_klines)
    except Exception as e:
        logger.warning(f"Failed to sync fresh klines from Bybit REST: {e}")

    # 2. Retrieve chronological klines from DB
    klines = db.get_latest_klines(symbol=symbol, interval=interval, limit=limit)

    from src.trading.agent.technical_analysis import TechnicalAnalyzer
    redis_client = get_trading_redis()
    ob = redis_client.get_orderbook(symbol)
    tech = TechnicalAnalyzer.analyze_full_market(klines, ob)

    return {
        "symbol": symbol,
        "interval": interval,
        "count": len(klines),
        "klines": [k.to_dict() for k in klines],
        "technical_indicators": tech
    }

@router.get("/orderbook")
async def get_orderbook_data(symbol: str = Query("BTCUSDT")):
    """Получение стакана и дисбаланса объемов из Redis."""
    redis_client = get_trading_redis()
    ob = redis_client.get_orderbook(symbol)
    if not ob:
        # Fallback to REST
        client = BybitRestClient()
        ob = client.get_orderbook(symbol, limit=25)
    return {"symbol": symbol, "orderbook": ob}

@router.get("/news")
async def get_news_rag(symbol: str = Query("BTC"), hours: int = Query(24)):
    """Получение 24-часового RAG контекста и сентимента из Qdrant."""
    rag = get_market_rag_service()
    clean_sym = symbol.replace("USDT", "").replace("PERP", "").upper()
    summary = rag.get_sentiment_summary(clean_sym, hours_back=hours)
    news_points = rag.query_24h_context(clean_sym, hours_back=hours, limit=10)
    return {
        "symbol": clean_sym,
        "sentiment_summary": summary,
        "articles": [p.payload for p in news_points]
    }

@router.get("/logs")
async def get_system_logs(limit: int = Query(50, ge=5, le=200)):
    """Получение последних системных логов и решений агента."""
    db = get_trading_db()
    with db.get_session() as session:
        logs = session.query(TradingSystemLog).order_by(TradingSystemLog.created_at.desc()).limit(limit).all()
        return {
            "count": len(logs),
            "logs": [l.to_dict() for l in logs]
        }

@router.get("/orders")
async def get_orders_history(limit: int = Query(50, ge=5, le=200)):
    """Получение истории выставленных ордеров."""
    db = get_trading_db()
    with db.get_session() as session:
        orders = session.query(TradingOrder).order_by(TradingOrder.created_at.desc()).limit(limit).all()
        return {
            "count": len(orders),
            "orders": [
                {
                    "id": o.id,
                    "order_id": o.order_id,
                    "order_link_id": o.order_link_id,
                    "symbol": o.symbol,
                    "side": o.side,
                    "order_type": o.order_type,
                    "price": float(o.price) if o.price else 0.0,
                    "qty": float(o.qty) if o.qty else 0.0,
                    "sl_price": float(o.sl_price) if o.sl_price else None,
                    "tp_price": float(o.tp_price) if o.tp_price else None,
                    "status": o.status,
                    "is_dry_run": o.is_dry_run,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in orders
            ]
        }

@router.post("/analyze")
async def analyze_market(req: AnalyzeRequest):
    """
    Запуск полного цикла LangGraph StateGraph анализа:
    Fetch Context -> Technical Analysis -> Gemini/Gemma Decision -> Localization & DB Log.
    """
    logger.info(f"Starting StateGraph analysis for {req.symbol} ({req.timeframe}m) in {req.mode} mode...")
    
    # Broadcast start event to UI
    await ws_manager.broadcast({
        "type": "ANALYSIS_STARTED",
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "mode": req.mode,
        "timestamp": int(time.time())
    })

    # Run StateGraph synchronously in thread pool to avoid blocking async event loop
    final_state = await asyncio.to_thread(
        run_trading_agent_analysis,
        symbol=req.symbol,
        timeframe=req.timeframe,
        mode=req.mode
    )

    decision = final_state.get("decision", {})
    tech = final_state.get("technical_indicators", {})

    # Broadcast completed decision to UI
    await ws_manager.broadcast({
        "type": "ANALYSIS_COMPLETED",
        "symbol": req.symbol,
        "mode": req.mode,
        "decision": decision,
        "technical_summary": {
            "current_price": tech.get("current_price"),
            "trend": tech.get("trend"),
            "rsi": tech.get("rsi", {}).get("value"),
            "imbalance": tech.get("orderbook_imbalance", {}).get("imbalance_ratio")
        }
    })

    return {
        "status": "success",
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "mode": req.mode,
        "decision": decision,
        "technical_indicators": tech,
        "news_summary": final_state.get("news_rag_context", {}).get("summary"),
        "logs": final_state.get("logs", [])
    }

@router.post("/execute")
async def execute_trade(req: ExecuteRequest):
    """
    Сквозной запуск:
    1. LangGraph StateGraph Анализ (Fast/Deep).
    2. Risk Engine математическая валидация и сайзинг.
    3. Исполнение на Bybit Unified V5 (или Dry-Run симуляция) с атомарными TP/SL.
    """
    logger.info(f"Starting End-to-End trade execution pipeline for {req.symbol} (Live: {req.live})...")

    # 1. StateGraph
    final_state = await asyncio.to_thread(
        run_trading_agent_analysis,
        symbol=req.symbol,
        timeframe=req.timeframe,
        mode=req.mode
    )

    decision = final_state.get("decision", {})
    decision["symbol"] = req.symbol

    # 2. Risk Engine & Execution
    exec_service = get_execution_service()
    exec_res = await asyncio.to_thread(
        exec_service.process_and_execute_signal,
        decision=decision,
        dry_run=not req.live
    )

    # Broadcast result
    await ws_manager.broadcast({
        "type": "EXECUTION_RESULT",
        "symbol": req.symbol,
        "live": req.live,
        "decision": decision,
        "execution": exec_res
    })

    return {
        "status": exec_res.get("status"),
        "decision": decision,
        "execution_result": exec_res,
        "technical_indicators": final_state.get("technical_indicators"),
    }

# --- WebSocket Endpoint ---

@router.websocket("/ws")
async def trading_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket поток реального времени для дашборда:
    - Котировки и стакан
    - Логи выполнения LangGraph
    - Алерты и статус позиций
    """
    await ws_manager.connect(websocket)
    try:
        # Отправляем приветственное сообщение и текущий статус
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "message": "Connected to Bybit Autonomous Trading WebSocket Hub",
            "timestamp": int(time.time())
        })
        while True:
            # Слушаем входящие сообщения/команды от клиента (например, пинг)
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": int(time.time())})
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket connection closed with exception: {e}")
        ws_manager.disconnect(websocket)
