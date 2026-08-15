import json
import time
import logging
from typing import List, Dict, Any, Optional
from collections import deque

from src.trading.news.models import RawNewsItem, NewsTriageResult, ProcessedCatalystEvent
from src.trading.news.triage import get_triage_engine, FastNewsTriageEngine
from src.trading.rest_client import BybitRestClient
from src.trading.rag import get_market_rag_service
from src.trading.redis_client import get_trading_redis, TradingRedisClient
from src.trading.db import get_trading_db

logger = logging.getLogger(__name__)

REDIS_CATALYST_FEED_KEY = "news:catalyst_feed"
REDIS_CATALYST_FEED_MAX = 50

class CatalystDispatcher:
    """
    Главный диспетчер архитектуры «News-First».
    Принимает сырые новости, прогоняет через Fast LLM Triage,
    проверяет наличие тикера на Bybit и запускает торговый контур LangGraph.
    """

    def __init__(self):
        self.triage_engine = get_triage_engine()
        self.bybit_client = BybitRestClient()
        self.rag_service = get_market_rag_service()
        self.redis: TradingRedisClient = get_trading_redis()
        self.db = get_trading_db()
        self._recent_events: deque = deque(maxlen=REDIS_CATALYST_FEED_MAX)
        self._bybit_symbols_set: set = set()
        self._last_bybit_sync_ts: float = 0.0

    def _sync_bybit_symbols_if_needed(self):
        """Периодическая синхронизация списка всех доступных линейных контрактов Bybit (кэш на 10 минут)."""
        now = time.time()
        if not self._bybit_symbols_set or (now - self._last_bybit_sync_ts > 600):
            try:
                res = self.bybit_client.client.get_tickers(category="linear")
                items = res.get("result", {}).get("list", [])
                if items:
                    self._bybit_symbols_set = set(t.get("symbol", "") for t in items if t.get("symbol"))
                    self._last_bybit_sync_ts = now
                    logger.info(f"CatalystDispatcher: Cached {len(self._bybit_symbols_set)} Bybit Linear Perpetual symbols.")
            except Exception as e:
                logger.warning(f"CatalystDispatcher: Failed to sync Bybit symbols list: {e}")

    def _check_bybit_availability(self, symbol: str) -> bool:
        """Проверка, торгуется ли бессрочный дериватив на Bybit."""
        if not symbol:
            return False
        self._sync_bybit_symbols_if_needed()
        clean = symbol.strip().upper()
        if clean in self._bybit_symbols_set:
            return True
        # Проверка без USDT или с USDT
        if not clean.endswith("USDT") and f"{clean}USDT" in self._bybit_symbols_set:
            return True
        return False

    def get_recent_feed(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Получение последних событий-катализаторов из Redis или памяти."""
        try:
            if self.redis.is_connected() and self.redis.client:
                items = self.redis.client.lrange(REDIS_CATALYST_FEED_KEY, 0, limit - 1)
                if items:
                    return [json.loads(x) for x in items]
        except Exception as e:
            logger.debug(f"Redis get_recent_feed error: {e}")
        return [e.model_dump() for e in list(self._recent_events)[:limit]]

    def process_incoming_news(self, news: RawNewsItem) -> ProcessedCatalystEvent:
        """
        Полный конвейер обработки новости News-First:
        1. Fast LLM Triage (< 1 сек)
        2. Bybit Instrument Resolver
        3. Определение статуса (MONITORED, PENDING_ANALYSIS, EXECUTED, UNLISTED)
        4. Запись в Qdrant
        5. Авто-запуск LangGraph при высокой важности (Impact >= 7)
        """
        # 1. Быстрая классификация
        triage = self.triage_engine.triage_news(news)

        event_id = news.id
        raw_sym = triage.symbol.strip().lstrip("$").upper() if triage.symbol else None
        
        bybit_symbol = None
        is_available = False

        if raw_sym:
            bybit_symbol = raw_sym if raw_sym.endswith("USDT") else f"{raw_sym}USDT"
            is_available = self._check_bybit_availability(bybit_symbol)

        # 2. Определение базового статуса
        if not bybit_symbol or not is_available:
            status = "UNLISTED" if raw_sym else "IGNORED"
        else:
            status = "MONITORED"

        # 3. Фильтр высокой значимости (Impact >= 7 & Tradable on Bybit)
        if triage.is_tradable and triage.impact_score >= 7 and triage.event_type != "NOISE" and is_available and bybit_symbol:
            status = "PENDING_ANALYSIS"
            logger.info(
                f"🔥 HIGH IMPACT CATALYST TRIGGERED: [{bybit_symbol}] "
                f"Impact={triage.impact_score}/10 Type={triage.event_type} "
                f"Sentiment={triage.sentiment}"
            )

            try:
                from src.trading.telegram import get_telegram_notifier
                get_telegram_notifier().notify_catalyst(
                    title=news.title,
                    symbol=triage.symbol,
                    impact_score=triage.impact_score,
                    event_type=triage.event_type,
                    sentiment=triage.sentiment
                )
            except Exception as _te:
                logger.debug(f"Telegram notify error: {_te}")

            # 4. Запись в Qdrant
            try:
                self.rag_service.sync_hot_movers_news([raw_sym.replace("USDT", "")])
            except Exception as e:
                logger.warning(f"Error vectorizing catalyst news: {e}")

            # 5. Запуск торгового контура LangGraph
            try:
                from src.trading.agent.graph import run_trading_agent_analysis
                from src.trading.execution.service import ExecutionService

                logger.info(f"Triggering LangGraph Catalyst Analysis for {bybit_symbol}...")
                agent_result = run_trading_agent_analysis(
                    symbol=bybit_symbol,
                    timeframe="15",
                    mode="fast"
                )

                decision = agent_result.get("decision")
                if decision:
                    status = "ANALYZED"
                    # Передача в ExecutionService
                    exec_service = ExecutionService()
                    exec_res = exec_service.process_and_execute_signal(
                        decision=decision,
                        dry_run=True # По умолчанию безопасный dry-run
                    )
                    if exec_res.get("status") in ["Simulated_Filled", "Executed"]:
                        status = "EXECUTED"
                    elif exec_res.get("status") == "Rejected":
                        status = "REJECTED_RISK"

            except Exception as e:
                logger.error(f"Error executing catalyst trading pipeline for {bybit_symbol}: {e}")

        event = ProcessedCatalystEvent(
            id=event_id,
            news=news,
            triage=triage,
            bybit_symbol=bybit_symbol,
            is_available_on_bybit=is_available,
            status=status
        )

        # Сохранение в ленту
        self._recent_events.appendleft(event)
        try:
            if self.redis.is_connected() and self.redis.client:
                self.redis.client.lpush(REDIS_CATALYST_FEED_KEY, json.dumps(event.model_dump()))
                self.redis.client.ltrim(REDIS_CATALYST_FEED_KEY, 0, REDIS_CATALYST_FEED_MAX - 1)
        except Exception as e:
            logger.debug(f"Redis cache catalyst feed error: {e}")

        # Логирование в базу
        self.db.log_event(
            component="CatalystDispatcher",
            message_en=f"Catalyst [{triage.symbol or 'N/A'}] Impact={triage.impact_score} ({triage.event_type}) -> Status: {status}",
            message_ru=f"Катализатор [{triage.symbol or 'N/A'}] Важность={triage.impact_score} ({triage.event_type}) -> Статус: {status}",
            level="INFO" if triage.impact_score < 7 else "WARNING",
            details=event.model_dump()
        )

        return event

_catalyst_dispatcher_instance: Optional[CatalystDispatcher] = None

def get_catalyst_dispatcher() -> CatalystDispatcher:
    global _catalyst_dispatcher_instance
    if _catalyst_dispatcher_instance is None:
        _catalyst_dispatcher_instance = CatalystDispatcher()
    return _catalyst_dispatcher_instance
