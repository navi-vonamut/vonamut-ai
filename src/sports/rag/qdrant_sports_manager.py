import logging
import hashlib
import uuid
import datetime
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.sports.config import sports_config

logger = logging.getLogger(__name__)

class QdrantSportsManager:
    """
    Векторный менеджер Qdrant для спортивного контекста (коллекция sports_context_24h).
    Содержит глобальный English-fallback в логах для стабильности мониторинга.
    """

    def __init__(self):
        self.config = sports_config
        self.client = QdrantClient(url=self.config.get_effective_qdrant_url())
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=self.config.embedding_model,
            google_api_key=self.config.google_api_key if self.config.google_api_key else None
        )

    def init_collection(self) -> bool:
        """Создает и настраивает коллекцию sports_context_24h в Qdrant."""
        col_name = self.config.qdrant_collection_name
        target_size = self.config.vector_size

        try:
            if self.client.collection_exists(col_name):
                info = self.client.get_collection(col_name)
                current_size = info.config.params.vectors.size
                if current_size != target_size:
                    logger.warning(
                        f"[RAG_SYNC] Qdrant collection {col_name} vector size {current_size} != {target_size}. Recreating..."
                    )
                    self.client.delete_collection(col_name)

            if not self.client.collection_exists(col_name):
                logger.info(f"[RAG_SYNC] Creating Qdrant collection {col_name} (size: {target_size})...")
                self.client.create_collection(
                    collection_name=col_name,
                    vectors_config=models.VectorParams(
                        size=target_size,
                        distance=models.Distance.COSINE
                    )
                )

            self._create_payload_indexes(col_name)
            logger.info(f"[RAG_SYNC] Collection {col_name} initialized successfully.")
            return True
        except Exception as e:
            logger.error(f"[RAG_SYNC] Failed to initialize Qdrant collection {col_name}: {e}")
            return False

    def _create_payload_indexes(self, col_name: str):
        """Создает индексы для быстрой выборки по командам и времени."""
        index_fields = [
            ("timestamp", models.PayloadSchemaType.INTEGER),
            ("team1", models.PayloadSchemaType.KEYWORD),
            ("team2", models.PayloadSchemaType.KEYWORD),
            ("source", models.PayloadSchemaType.KEYWORD),
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
                pass

    def add_insider_post(self, post_data: Dict[str, Any]) -> bool:
        """
        Векторизация и сохранение 1 инсайдерского сообщения в Qdrant.
        English-fallback logging: [RAG_SYNC] Vectorized X posts for Team1 vs Team2
        """
        return self.add_insider_posts_batch([post_data]) > 0

    def add_insider_posts_batch(self, posts: List[Dict[str, Any]]) -> int:
        """
        Векторизация и добавление пакета постов в Qdrant.
        """
        if not posts:
            return 0

        self.init_collection()
        col_name = self.config.qdrant_collection_name
        texts_to_embed = []
        valid_posts = []

        for p in posts:
            text = p.get("text", "")
            if not text:
                continue
            content_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

            # Проверка дубликатов
            if self._is_post_indexed(content_hash):
                continue

            texts_to_embed.append(text)
            p["content_hash"] = content_hash
            valid_posts.append(p)

        if not texts_to_embed:
            return 0

        try:
            embeddings_vectors = self.embeddings.embed_documents(texts_to_embed)
            points = []

            for i, p in enumerate(valid_posts):
                point_id = str(uuid.uuid4())
                team1 = p.get("team1", "Unknown")
                team2 = p.get("team2", "Unknown")
                
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=embeddings_vectors[i],
                        payload={
                            "text": p["text"],
                            "team1": team1,
                            "team2": team2,
                            "source": p.get("source", "telegram"),
                            "timestamp": int(p.get("timestamp", datetime.datetime.utcnow().timestamp())),
                            "timestamp_dt": p.get("timestamp_dt", datetime.datetime.utcnow().isoformat()),
                            "content_hash": p["content_hash"]
                        }
                    )
                )

            self.client.upsert(collection_name=col_name, points=points)

            # English-fallback logging по требованию этапа 2
            team1_clean = valid_posts[0].get("team1", "Team 1")
            team2_clean = valid_posts[0].get("team2", "Team 2")
            logger.info(f"[RAG_SYNC] Vectorized {len(points)} posts for {team1_clean} vs {team2_clean}")
            return len(points)
        except Exception as e:
            logger.error(f"[RAG_SYNC] Error inserting posts into Qdrant: {e}")
            return 0

    def _is_post_indexed(self, content_hash: str) -> bool:
        """Проверка наличия поста по хешу содержимого."""
        try:
            res = self.client.scroll(
                collection_name=self.config.qdrant_collection_name,
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
        except Exception:
            return False

    def query_match_context(self, team1: str, team2: str, hours_back: int = 48, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Векторный и контекстный поиск новостей по паре команд за последние hours_back часов.
        """
        col_name = self.config.qdrant_collection_name
        min_ts = int((datetime.datetime.utcnow() - datetime.timedelta(hours=hours_back)).timestamp())

        query_text = f"Новости, травмы, составы, инсайды {team1} {team2}"

        try:
            query_vector = self.embeddings.embed_query(query_text)

            filter_cond = models.Filter(
                must=[
                    models.FieldCondition(
                        key="timestamp",
                        range=models.Range(gte=min_ts)
                    )
                ]
            )

            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=col_name,
                    query=query_vector,
                    query_filter=filter_cond,
                    limit=limit
                )
                hits = response.points
            elif hasattr(self.client, "search_points"):
                hits = self.client.search_points(
                    collection_name=col_name,
                    vector=query_vector,
                    query_filter=filter_cond,
                    limit=limit
                )
            else:
                hits = self.client.search(
                    collection_name=col_name,
                    query_vector=query_vector,
                    query_filter=filter_cond,
                    limit=limit
                )

            results = []
            for h in hits:
                p = dict(h.payload or {})
                p["score"] = h.score
                results.append(p)

            logger.info(f"[RAG_SYNC] Retrieved {len(results)} context posts for query '{team1} vs {team2}'")
            return results
        except Exception as e:
            logger.error(f"[RAG_SYNC] Error querying sports context from Qdrant: {e}")
            return []

_qdrant_sports_instance: Optional[QdrantSportsManager] = None

def get_qdrant_sports_manager() -> QdrantSportsManager:
    global _qdrant_sports_instance
    if _qdrant_sports_instance is None:
        _qdrant_sports_instance = QdrantSportsManager()
    return _qdrant_sports_instance
