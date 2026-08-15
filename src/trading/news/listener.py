import time
import json
import logging
import threading
import hashlib
from typing import List, Dict, Any, Optional

from src.trading.news.models import RawNewsItem
from src.trading.redis_client import get_trading_redis, TradingRedisClient
from src.trading.rag.news_fetcher import NewsFetcher

logger = logging.getLogger(__name__)

REDIS_NEWS_SEEN_PREFIX = "news:seen:"
REDIS_NEWS_SEEN_TTL = 86400 # 24 hours
REDIS_RAW_NEWS_CHANNEL = "channel:news_raw"

class NewsStreamListener:
    """
    Потоковый слушатель входящих новостей (News Firehose Listener).
    Опрашивает источники каждые 15–30 секунд, дедуплицирует через Redis L1
    и передает в очередь быстрой LLM-сортировки (Fast Triage).
    """

    def __init__(self, poll_interval_sec: int = 20):
        self.poll_interval = poll_interval_sec
        self.fetcher = NewsFetcher()
        self.redis: TradingRedisClient = get_trading_redis()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _compute_hash(self, url: str, title: str) -> str:
        raw = f"{url.strip().lower()}|{title.strip().lower()}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def is_news_seen(self, content_hash: str) -> bool:
        """Проверка дедупликации через Redis L1 Cache."""
        try:
            if self.redis.is_connected() and self.redis.client:
                key = f"{REDIS_NEWS_SEEN_PREFIX}{content_hash}"
                return bool(self.redis.client.exists(key))
        except Exception as e:
            logger.debug(f"Redis is_news_seen error: {e}")
        return False

    def mark_news_seen(self, content_hash: str):
        """Отметка новости как обработанной с TTL 24 часа."""
        try:
            if self.redis.is_connected() and self.redis.client:
                key = f"{REDIS_NEWS_SEEN_PREFIX}{content_hash}"
                self.redis.client.setex(key, REDIS_NEWS_SEEN_TTL, "1")
        except Exception as e:
            logger.debug(f"Redis mark_news_seen error: {e}")

    def publish_raw_news(self, item: RawNewsItem):
        """Публикация в Redis Pub/Sub и вызов диспетчера."""
        try:
            if self.redis.is_connected() and self.redis.client:
                self.redis.client.publish(REDIS_RAW_NEWS_CHANNEL, json.dumps(item.model_dump()))
        except Exception as e:
            logger.debug(f"Redis publish_raw_news error: {e}")

        # Прямая передача в диспетчер катализаторов
        try:
            from src.trading.news.dispatcher import get_catalyst_dispatcher
            dispatcher = get_catalyst_dispatcher()
            dispatcher.process_incoming_news(item)
        except Exception as e:
            logger.error(f"Error dispatching incoming news item: {e}")

    def poll_new_articles(self, max_per_poll: int = 5) -> List[RawNewsItem]:
        """Опрос внешних источников и сбор только новых уникальных статей с контролем нагрузки."""
        raw_articles = self.fetcher.fetch_all_sources()
        new_items: List[RawNewsItem] = []

        for a in raw_articles:
            if len(new_items) >= max_per_poll:
                break
            chash = self._compute_hash(a.url, a.title)
            if not self.is_news_seen(chash):
                self.mark_news_seen(chash)
                item = RawNewsItem(
                    id=chash,
                    title=a.title,
                    content=a.content,
                    url=a.url,
                    source=a.source,
                    timestamp=a.timestamp,
                    published_at=a.timestamp_dt,
                    content_hash=chash,
                )
                new_items.append(item)
                self.publish_raw_news(item)
                # Плавная пауза между статьями
                time.sleep(1.0)

        if new_items:
            logger.info(f"NewsStreamListener: Discovered {len(new_items)} fresh unique breaking news items.")

        return new_items

    def _loop(self):
        logger.info(f"NewsStreamListener background loop started (interval={self.poll_interval}s).")
        while self._running:
            try:
                self.poll_new_articles()
            except Exception as e:
                logger.error(f"Error in NewsStreamListener polling loop: {e}")

            for _ in range(self.poll_interval):
                if not self._running:
                    break
                time.sleep(1)

    def start_background(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="NewsStreamListener")
        self._thread.start()
        logger.info("NewsStreamListener thread started.")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
            logger.info("NewsStreamListener thread stopped.")

_news_listener_instance: Optional[NewsStreamListener] = None

def get_news_stream_listener() -> NewsStreamListener:
    global _news_listener_instance
    if _news_listener_instance is None:
        _news_listener_instance = NewsStreamListener()
    return _news_listener_instance
