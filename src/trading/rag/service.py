import time
import logging
from typing import List, Dict, Any, Optional

from src.trading.rag.config import rag_config, RAGConfig
from src.trading.rag.qdrant_manager import get_qdrant_news_manager, QdrantNewsManager
from src.trading.rag.news_fetcher import NewsFetcher, NewsArticle
from src.trading.db import get_trading_db

logger = logging.getLogger(__name__)

class MarketRAGService:
    """
    Главный сервис RAG (Новостной фон и текстовая аналитика).
    Обеспечивает:
    1. Сбор и векторизацию новостей через gemini-embedding-2 (3072d) в Qdrant.
    2. Поиск контекста с жесткой фильтрацией за последние 24 часа.
    3. Расчет сводного индекса настроения (Sentiment Index) и выявление катализаторов.
    """

    def __init__(
        self,
        config: Optional[RAGConfig] = None,
        qdrant_manager: Optional[QdrantNewsManager] = None
    ):
        self.config = config or rag_config
        self.qdrant = qdrant_manager or get_qdrant_news_manager()
        self.fetcher = NewsFetcher(self.config)
        self.db = get_trading_db()

    def initialize(self) -> bool:
        """Инициализация коллекции Qdrant."""
        logger.info("Initializing MarketRAGService...")
        ok = self.qdrant.init_collection()
        if ok:
            self.db.log_event(
                component="MarketRAGService",
                message_en=f"Market RAG service initialized with collection '{self.config.collection_name}' (gemini-embedding-2)",
                message_ru=f"Сервис RAG инициализирован с коллекцией '{self.config.collection_name}' (gemini-embedding-2)",
                level="INFO"
            )
        return ok

    def sync_news(self, force: bool = False) -> Dict[str, int]:
        """
        Сбор свежих новостей из всех источников и запись новых статей в Qdrant.
        """
        logger.info("Starting news collection and vectorization...")
        articles = self.fetcher.fetch_all_sources()

        new_articles = []
        for a in articles:
            if force or not self.qdrant.is_article_indexed(a.content_hash):
                new_articles.append(a.model_dump())

        logger.info(f"Found {len(new_articles)} new articles to index (out of {len(articles)} fetched).")

        indexed_count = 0
        if new_articles:
            # Пакетами по 20 для надежности
            batch_size = 20
            for i in range(0, len(new_articles), batch_size):
                chunk = new_articles[i:i + batch_size]
                indexed_count += self.qdrant.insert_news_batch(chunk)

        self.db.log_event(
            component="MarketRAGService",
            message_en=f"News sync complete: {indexed_count} new articles indexed in Qdrant.",
            message_ru=f"Синхронизация новостей завершена: {indexed_count} новых статей проиндексировано в Qdrant.",
            level="INFO",
            details={"fetched": len(articles), "indexed": indexed_count}
        )

        return {"fetched": len(articles), "indexed": indexed_count}

    def sync_hot_movers_news(self, hot_symbols: List[str]) -> Dict[str, int]:
        """
        Целевая синхронизация инфо-поля для топ-монет, найденных Market Screener.
        """
        if not hot_symbols:
            return {"fetched": 0, "indexed": 0}

        logger.info(f"RAG: Synchronizing hot movers news for: {hot_symbols}...")
        articles = self.fetcher.fetch_hot_symbols_news(hot_symbols)

        new_articles = []
        for a in articles:
            if not self.qdrant.is_article_indexed(a.content_hash):
                new_articles.append(a.model_dump())

        logger.info(f"RAG: Found {len(new_articles)} new targeted articles to index in Qdrant.")
        indexed_count = 0
        if new_articles:
            batch_size = 15
            for i in range(0, len(new_articles), batch_size):
                chunk = new_articles[i:i + batch_size]
                indexed_count += self.qdrant.insert_news_batch(chunk)

        self.db.log_event(
            component="MarketRAGService",
            message_en=f"Hot movers news sync: {indexed_count} new articles indexed for {hot_symbols}",
            message_ru=f"Синхронизация новостей горячих пар: {indexed_count} новых статей проиндексировано для {hot_symbols}",
            level="INFO",
            details={"symbols": hot_symbols, "fetched": len(articles), "indexed": indexed_count}
        )

        return {"fetched": len(articles), "indexed": indexed_count}

    def query_24h_context(
        self,
        symbol: str,
        query: Optional[str] = None,
        hours_back: int = 24,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Запрос релевантного контекста за последние N часов для указанного тикера.
        """
        now_ms = int(time.time() * 1000)
        min_ts_ms = now_ms - (hours_back * 60 * 60 * 1000)

        search_query = query or f"Market news price action and drivers for {symbol}"
        results = self.qdrant.query_news(
            query=search_query,
            symbol=symbol,
            min_timestamp_ms=min_ts_ms,
            limit=limit
        )
        return results

    def get_sentiment_summary(self, symbol: str, hours_back: int = 24) -> Dict[str, Any]:
        """
        Агрегация новостного фона и расчет сентимента за последние N часов.
        """
        now_ms = int(time.time() * 1000)
        min_ts_ms = now_ms - (hours_back * 60 * 60 * 1000)

        articles = self.qdrant.get_recent_news_by_time(
            min_timestamp_ms=min_ts_ms,
            symbol=symbol,
            limit=50
        )

        bullish_count = sum(1 for a in articles if a.get("sentiment") == "bullish")
        bearish_count = sum(1 for a in articles if a.get("sentiment") == "bearish")
        neutral_count = sum(1 for a in articles if a.get("sentiment") == "neutral")
        total = len(articles)

        if total > 0:
            score = (bullish_count - bearish_count) / total
        else:
            score = 0.0

        if score >= 0.35:
            mood = "STRONG_BULLISH"
        elif score >= 0.1:
            mood = "BULLISH"
        elif score <= -0.35:
            mood = "STRONG_BEARISH"
        elif score <= -0.1:
            mood = "BEARISH"
        else:
            mood = "NEUTRAL"

        # Ключевые катализаторы (High impact)
        key_catalysts = [
            f"[{a.get('source')}] {a.get('title')} ({a.get('sentiment')})"
            for a in articles if a.get("importance") == "high"
        ][:5]

        return {
            "symbol": symbol,
            "hours_back": hours_back,
            "total_articles": total,
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "neutral_count": neutral_count,
            "sentiment_score": round(score, 3), # от -1.0 до +1.0
            "mood": mood,
            "key_catalysts": key_catalysts,
        }

    def format_context_for_prompt(self, symbol: str, hours_back: int = 24) -> str:
        """
        Форматирование текстового контекста для промпта LangGraph агента.
        """
        summary = self.get_sentiment_summary(symbol, hours_back=hours_back)
        articles = self.query_24h_context(symbol, limit=4, hours_back=hours_back)

        lines = [
            f"### News & Market Sentiment (Last {hours_back}h for {symbol})",
            f"- **Market Mood**: {summary['mood']} (Score: {summary['sentiment_score']})",
            f"- **Stats**: Bullish: {summary['bullish_count']} | Bearish: {summary['bearish_count']} | Neutral: {summary['neutral_count']}",
        ]

        if summary["key_catalysts"]:
            lines.append("- **Key Catalysts**:")
            for cat in summary["key_catalysts"]:
                lines.append(f"  * {cat}")

        if articles:
            lines.append("- **Top Relevant News Context**:")
            for a in articles:
                lines.append(f"  * [{a.get('source')}] {a.get('title')} (Relevance: {round(a.get('score', 0), 2)})")

        return "\n".join(lines)

_rag_service_instance: Optional[MarketRAGService] = None

def get_market_rag_service() -> MarketRAGService:
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = MarketRAGService()
    return _rag_service_instance
