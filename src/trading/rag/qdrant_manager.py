import logging
import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.trading.rag.config import rag_config, RAGConfig

logger = logging.getLogger(__name__)

class QdrantNewsManager:
    """
    Менеджер векторной базы данных Qdrant для новостного фона и аналитики рынка.
    Использует модель эмбеддингов Google `gemini-embedding-2` (3072 размерность).
    """

    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or rag_config
        self.client = QdrantClient(url=self.config.get_effective_qdrant_url())
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=self.config.embedding_model,
            google_api_key=self.config.google_api_key if self.config.google_api_key else None
        )

    def init_collection(self):
        """Инициализация коллекции market_news_24h и создание индексов полей."""
        col_name = self.config.collection_name
        target_size = self.config.vector_size

        try:
            if self.client.collection_exists(col_name):
                info = self.client.get_collection(col_name)
                current_size = info.config.params.vectors.size
                if current_size != target_size:
                    logger.warning(
                        f"Qdrant collection {col_name} has size {current_size} != {target_size}. Recreating..."
                    )
                    self.client.delete_collection(col_name)

            if not self.client.collection_exists(col_name):
                logger.info(f"Creating Qdrant collection {col_name} with size {target_size} (gemini-embedding-2)...")
                self.client.create_collection(
                    collection_name=col_name,
                    vectors_config=models.VectorParams(
                        size=target_size,
                        distance=models.Distance.COSINE
                    )
                )

            # Создание Payload индексов для быстрой фильтрации по времени и тикерам
            self._create_payload_indexes(col_name)
            logger.info(f"Qdrant collection {col_name} is ready.")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant collection {col_name}: {e}")
            raise

    def _create_payload_indexes(self, col_name: str):
        """Создание индексов полей полезной нагрузки."""
        index_fields = [
            ("timestamp", models.PayloadSchemaType.INTEGER),
            ("symbols", models.PayloadSchemaType.KEYWORD),
            ("sentiment", models.PayloadSchemaType.KEYWORD),
            ("source", models.PayloadSchemaType.KEYWORD),
            ("importance", models.PayloadSchemaType.KEYWORD),
            ("content_hash", models.PayloadSchemaType.KEYWORD),
        ]
        for field_name, field_type in index_fields:
            try:
                self.client.create_payload_index(
                    collection_name=col_name,
                    field_name=field_name,
                    field_schema=field_type
                )
            except Exception:
                # Индекс уже может существовать
                pass

    def check_connection(self) -> bool:
        """Проверка доступности сервера Qdrant."""
        try:
            collections = self.client.get_collections()
            return collections is not None
        except Exception as e:
            logger.error(f"Qdrant connection check failed: {e}")
            return False

    def is_article_indexed(self, content_hash: str) -> bool:
        """Проверка, была ли новость уже проиндексирована (дедупликация)."""
        try:
            res = self.client.scroll(
                collection_name=self.config.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="content_hash",
                            match=models.MatchValue(value=content_hash)
                        )
                    ]
                ),
                limit=1,
                with_payload=False,
                with_vectors=False
            )
            points, _ = res
            return len(points) > 0
        except Exception as e:
            logger.warning(f"Error checking article existence in Qdrant: {e}")
            return False

    def insert_news_batch(self, articles: List[Dict[str, Any]]) -> int:
        """
        Векторизация и сохранение пакета новостей в Qdrant.
        """
        if not articles:
            return 0

        texts_to_embed = []
        valid_articles = []

        for art in articles:
            # Текст для векторизации: Заголовок + Описание + Тональность
            content_text = f"Title: {art['title']}\nContent: {art['content']}"
            if art.get("symbols"):
                content_text += f"\nAssets: {', '.join(art['symbols'])}"
            texts_to_embed.append(content_text)
            valid_articles.append(art)

        try:
            # Генерация векторных эмбеддингов через gemini-embedding-2
            logger.info(f"Generating embeddings for {len(texts_to_embed)} articles using {self.config.embedding_model}...")
            embeddings_vectors = self.embeddings.embed_documents(texts_to_embed)

            points = []
            for i, art in enumerate(valid_articles):
                point_id = art.get("id") or str(uuid.uuid4())
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=embeddings_vectors[i],
                        payload={
                            "title": art["title"],
                            "content": art["content"],
                            "url": art.get("url", ""),
                            "source": art.get("source", "unknown"),
                            "symbols": art.get("symbols", []),
                            "sentiment": art.get("sentiment", "neutral"),
                            "importance": art.get("importance", "medium"),
                            "timestamp": int(art["timestamp"]),
                            "timestamp_dt": art.get("timestamp_dt", ""),
                            "content_hash": art.get("content_hash", ""),
                        }
                    )
                )

            self.client.upsert(
                collection_name=self.config.collection_name,
                points=points
            )
            logger.info(f"Successfully indexed {len(points)} news points in Qdrant.")
            return len(points)
        except Exception as e:
            logger.error(f"Error during insert_news_batch in Qdrant: {e}")
            raise

    def query_news(
        self,
        query: str,
        symbol: Optional[str] = None,
        min_timestamp_ms: Optional[int] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Векторный поиск релевантного контекста с фильтрацией по времени и активу.
        """
        filter_conditions = []

        # 1. Фильтр по времени (например, последние 24 часа)
        if min_timestamp_ms:
            filter_conditions.append(
                models.FieldCondition(
                    key="timestamp",
                    range=models.Range(gte=min_timestamp_ms)
                )
            )

        # 2. Фильтр по символу
        if symbol:
            clean_sym = symbol.replace("USDT", "").replace("PERP", "").upper()
            filter_conditions.append(
                models.FieldCondition(
                    key="symbols",
                    match=models.MatchAny(any=[clean_sym, symbol.upper(), "MACRO", "CRYPTO", "ALL"])
                )
            )

        qdrant_filter = models.Filter(must=filter_conditions) if filter_conditions else None

        try:
            # Получение вектора запроса
            query_vector = self.embeddings.embed_query(query)

            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.config.collection_name,
                    query=query_vector,
                    query_filter=qdrant_filter,
                    limit=limit
                )
                search_results = response.points
            elif hasattr(self.client, "search_points"):
                search_results = self.client.search_points(
                    collection_name=self.config.collection_name,
                    vector=query_vector,
                    query_filter=qdrant_filter,
                    limit=limit
                )
            else:
                search_results = self.client.search(
                    collection_name=self.config.collection_name,
                    query_vector=query_vector,
                    query_filter=qdrant_filter,
                    limit=limit
                )

            results = []
            for hit in search_results:
                item = dict(hit.payload or {})
                item["score"] = hit.score
                results.append(item)
            return results
        except Exception as e:
            logger.error(f"Error querying news in Qdrant: {e}")
            return []

    def get_recent_news_by_time(
        self,
        min_timestamp_ms: int,
        symbol: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Получение всех последних новостей за временное окно (без векторного запроса).
        """
        filter_conditions = [
            models.FieldCondition(
                key="timestamp",
                range=models.Range(gte=min_timestamp_ms)
            )
        ]
        if symbol:
            clean_sym = symbol.replace("USDT", "").replace("PERP", "").upper()
            filter_conditions.append(
                models.FieldCondition(
                    key="symbols",
                    match=models.MatchAny(any=[clean_sym, symbol.upper(), "MACRO", "CRYPTO", "ALL"])
                )
            )

        try:
            res = self.client.scroll(
                collection_name=self.config.collection_name,
                scroll_filter=models.Filter(must=filter_conditions),
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            points, _ = res
            return [p.payload for p in points]
        except Exception as e:
            logger.error(f"Error scrolling recent news from Qdrant: {e}")
            return []

_qdrant_manager_instance: Optional[QdrantNewsManager] = None

def get_qdrant_news_manager() -> QdrantNewsManager:
    global _qdrant_manager_instance
    if _qdrant_manager_instance is None:
        _qdrant_manager_instance = QdrantNewsManager()
    return _qdrant_manager_instance
