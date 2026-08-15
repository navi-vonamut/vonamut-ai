"""
RAG and News Analytics module for Trading Agent with Qdrant and Gemini-Embedding-2.
"""

from src.trading.rag.config import rag_config, RAGConfig
from src.trading.rag.qdrant_manager import QdrantNewsManager, get_qdrant_news_manager
from src.trading.rag.news_fetcher import NewsFetcher, NewsArticle
from src.trading.rag.service import MarketRAGService, get_market_rag_service

get_rag_service = get_market_rag_service

__all__ = [
    "rag_config",
    "RAGConfig",
    "QdrantNewsManager",
    "get_qdrant_news_manager",
    "NewsFetcher",
    "NewsArticle",
    "MarketRAGService",
    "get_market_rag_service",
    "get_rag_service",
]
