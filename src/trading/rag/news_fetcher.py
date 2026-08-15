import time
import hashlib
import logging
import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import httpx
from bs4 import BeautifulSoup
from tavily import TavilyClient

from src.trading.rag.config import rag_config, RAGConfig

logger = logging.getLogger(__name__)

class NewsArticle(BaseModel):
    id: str = Field(default_factory=lambda: "")
    title: str
    content: str
    url: str = ""
    source: str = "web"
    symbols: List[str] = Field(default_factory=list)
    sentiment: str = "neutral" # bullish, bearish, neutral
    importance: str = "medium" # high, medium, low
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    timestamp_dt: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    content_hash: str = ""

class NewsFetcher:
    """
    Сборщик и нормализатор новостей и рыночной аналитики из Tavily и RSS лент.
    """

    RSS_FEEDS = [
        {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss"},
        {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss"},
        {"name": "Decrypt", "url": "https://decrypt.co/feed"},
        {"name": "BeInCrypto", "url": "https://beincrypto.com/feed/"},
        {"name": "BitcoinMagazine", "url": "https://bitcoinmagazine.com/feed"},
    ]

    TICKER_KEYWORDS = {
        "BTC": ["bitcoin", "btc", "satoshi"],
        "ETH": ["ethereum", "eth", "vitalik", "ether"],
        "SOL": ["solana", "sol"],
        "MACRO": ["fed", "federal reserve", "inflation", "cpi", "powell", "interest rate", "sec", "etf", "macro", "treasury"],
    }

    BULLISH_WORDS = {
        "surge", "rally", "gain", "high", "jump", "bullish", "inflow", "breakout",
        "support", "buy", "adoption", "profit", "soar", "ath", "climb", "accumulate"
    }
    BEARISH_WORDS = {
        "drop", "fall", "crash", "plunge", "bearish", "outflow", "dump", "sell",
        "sec lawsuit", "hack", "exploit", "ban", "loss", "liquidat", "low", "panic"
    }

    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or rag_config
        self.tavily_client = TavilyClient(api_key=self.config.tavily_api_key) if self.config.tavily_api_key else None

    def _compute_hash(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _extract_symbols(self, text: str) -> List[str]:
        text_lower = text.lower()
        symbols = set()
        for sym, keywords in self.TICKER_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    symbols.add(sym)
                    break
        return list(symbols) if symbols else ["CRYPTO"]

    def _detect_sentiment(self, text: str) -> str:
        text_lower = text.lower()
        bull_score = sum(1 for w in self.BULLISH_WORDS if w in text_lower)
        bear_score = sum(1 for w in self.BEARISH_WORDS if w in text_lower)

        if bull_score > bear_score + 1:
            return "bullish"
        elif bear_score > bull_score + 1:
            return "bearish"
        return "neutral"

    def _detect_importance(self, title: str, symbols: List[str]) -> str:
        title_lower = title.lower()
        high_impact_keywords = ["fed", "rate cut", "rate hike", "sec", "approval", "binance", "etf inflow", "cpi", "war", "tariff"]
        if any(k in title_lower for k in high_impact_keywords) or "MACRO" in symbols:
            return "high"
        return "medium"

    def search_news(self, query: str, max_results: int = 10) -> List[NewsArticle]:
        """
        Универсальный бесплатный поисковик новостей (Google News RSS + Crypto Feeds).
        Не имеет ограничений по тарифным планам, работает 24/7 в режиме реального времени.
        """
        import urllib.parse
        articles: List[NewsArticle] = []
        now_ms = int(time.time() * 1000)

        # 1. Поиск через Google News RSS Engine (100% Free & Unlimited)
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            q_encoded = urllib.parse.quote(query)
            url = f"https://news.google.com/rss/search?q={q_encoded}&hl=en-US&gl=US&ceid=US:en"

            with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, "xml")
                    items = soup.find_all("item")[:max_results]
                    for item in items:
                        title_elem = item.find("title")
                        link_elem = item.find("link")
                        pub_elem = item.find("pubDate")
                        desc_elem = item.find("description")

                        title = title_elem.get_text().strip() if title_elem else ""
                        link = link_elem.get_text().strip() if link_elem else ""
                        pub_date = pub_elem.get_text().strip() if pub_elem else datetime.datetime.utcnow().isoformat()
                        raw_desc = desc_elem.get_text().strip() if desc_elem else ""
                        desc = BeautifulSoup(raw_desc, "html.parser").get_text() if raw_desc else title

                        if not title:
                            continue

                        full_text = f"{title} {desc}"
                        symbols = self._extract_symbols(full_text)
                        sentiment = self._detect_sentiment(full_text)
                        importance = self._detect_importance(title, symbols)
                        chash = self._compute_hash(link or title)

                        # Извлечение источника из заголовка (например "Title - SourceName")
                        source_name = "GoogleNews"
                        if " - " in title:
                            source_name = title.split(" - ")[-1].strip()

                        articles.append(
                            NewsArticle(
                                id=chash,
                                title=title,
                                content=desc,
                                url=link,
                                source=source_name,
                                symbols=symbols,
                                sentiment=sentiment,
                                importance=importance,
                                timestamp=now_ms,
                                timestamp_dt=pub_date,
                                content_hash=chash,
                            )
                        )
                    logger.info(f"Fetched {len(articles)} articles from Google News search for '{query[:40]}'.")
                    if articles:
                        return articles
        except Exception as e:
            logger.debug(f"Google News search error for '{query}': {e}")

        # 2. Fallback на Tavily только если ключ доступен и не исчерпан
        if self.tavily_client:
            try:
                res = self.tavily_client.search(query=query, search_depth="basic", max_results=max_results)
                for item in res.get("results", []):
                    title = item.get("title", "").strip()
                    content = item.get("content", "").strip()
                    url = item.get("url", "")
                    if title and content:
                        full_text = f"{title} {content}"
                        symbols = self._extract_symbols(full_text)
                        chash = self._compute_hash(url or title)
                        articles.append(
                            NewsArticle(
                                id=chash,
                                title=title,
                                content=content,
                                url=url,
                                source="Tavily",
                                symbols=symbols,
                                sentiment=self._detect_sentiment(full_text),
                                importance=self._detect_importance(title, symbols),
                                timestamp=now_ms,
                                timestamp_dt=datetime.datetime.utcnow().isoformat(),
                                content_hash=chash,
                            )
                        )
                return articles
            except Exception as e:
                logger.debug(f"Tavily secondary search skipped: {e}")

        return articles

    def fetch_rss_feed(self, feed_name: str, feed_url: str, limit: int = 15) -> List[NewsArticle]:
        """Сбор новостей из RSS ленты."""
        articles = []
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(feed_url)
                if resp.status_code != 200:
                    logger.warning(f"Failed to fetch RSS {feed_name}: status {resp.status_code}")
                    return []

                soup = BeautifulSoup(resp.content, "xml")
                items = soup.find_all("item")[:limit]
                now_ms = int(time.time() * 1000)

                for item in items:
                    title_elem = item.find("title")
                    desc_elem = item.find("description") or item.find("content:encoded")
                    link_elem = item.find("link")
                    pubdate_elem = item.find("pubDate")

                    title = title_elem.get_text().strip() if title_elem else ""
                    # Очистка HTML тегов из описания
                    raw_desc = desc_elem.get_text().strip() if desc_elem else ""
                    desc = BeautifulSoup(raw_desc, "html.parser").get_text() if raw_desc else ""
                    url = link_elem.get_text().strip() if link_elem else ""

                    if not title:
                        continue

                    full_text = f"{title} {desc}"
                    symbols = self._extract_symbols(full_text)
                    sentiment = self._detect_sentiment(full_text)
                    importance = self._detect_importance(title, symbols)
                    chash = self._compute_hash(url or title)

                    art = NewsArticle(
                        id=chash,
                        title=title,
                        content=desc or title,
                        url=url,
                        source=feed_name,
                        symbols=symbols,
                        sentiment=sentiment,
                        importance=importance,
                        timestamp=now_ms,
                        timestamp_dt=datetime.datetime.utcnow().isoformat(),
                        content_hash=chash,
                    )
                    articles.append(art)
                logger.info(f"Fetched {len(articles)} articles from RSS {feed_name}.")
                return articles
        except Exception as e:
            logger.error(f"Error parsing RSS {feed_name}: {e}")
            return []

    def fetch_cryptopanic_news(self, symbols: Optional[List[str]] = None, limit: int = 20) -> List[NewsArticle]:
        """
        Сбор новостей из CryptoPanic API (или публичного RSS потока).
        """
        articles: List[NewsArticle] = []
        now_ms = int(time.time() * 1000)

        # 1. Попытка через API токен если задан
        if self.config.cryptopanic_api_key:
            try:
                curr_param = ",".join(symbols) if symbols else ""
                url = f"https://cryptopanic.com/api/free/v1/posts/?auth_token={self.config.cryptopanic_api_key}&public=true"
                if curr_param:
                    url += f"&currencies={curr_param}"
                
                with httpx.Client(timeout=10.0) as client:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        for post in data.get("results", [])[:limit]:
                            title = post.get("title", "").strip()
                            url_post = post.get("url", "")
                            domain = post.get("domain", "CryptoPanic")
                            created_at = post.get("created_at") or datetime.datetime.utcnow().isoformat()
                            
                            currencies = [c.get("code", "").upper() for c in post.get("currencies", []) if c.get("code")]
                            if not currencies and symbols:
                                currencies = symbols

                            full_text = title
                            sentiment = self._detect_sentiment(full_text)
                            importance = self._detect_importance(title, currencies)
                            chash = self._compute_hash(url_post or title)

                            articles.append(
                                NewsArticle(
                                    id=chash,
                                    title=title,
                                    content=f"{title} (Source: {domain})",
                                    url=url_post,
                                    source=f"CryptoPanic/{domain}",
                                    symbols=currencies or ["CRYPTO"],
                                    sentiment=sentiment,
                                    importance=importance,
                                    timestamp=now_ms,
                                    timestamp_dt=created_at,
                                    content_hash=chash,
                                )
                            )
                        logger.info(f"Fetched {len(articles)} posts from CryptoPanic API.")
                        return articles
            except Exception as e:
                logger.debug(f"CryptoPanic API fetch failed: {e}")

        return []

    def fetch_hot_symbols_news(self, symbols: List[str]) -> List[NewsArticle]:
        """
        Целевой сбор новостей и фундаментальных катализаторов по списку горячих монет из Скринера.
        """
        all_articles: Dict[str, NewsArticle] = {}
        clean_symbols = [s.replace("USDT", "").replace("PERP", "").upper() for s in symbols if s]

        # 1. CryptoPanic по тикерам
        cp_news = self.fetch_cryptopanic_news(symbols=clean_symbols, limit=15)
        for a in cp_news:
            all_articles[a.content_hash] = a

        # 2. Целевой Google News / Web поиск по конкретным горячим монетам
        for sym in clean_symbols[:5]:
            q = f"{sym} crypto coin token price catalysts news today"
            search_articles = self.search_news(q, max_results=4)
            for a in search_articles:
                if sym not in a.symbols:
                    a.symbols.append(sym)
                all_articles[a.content_hash] = a

        logger.info(f"Targeted news fetch for {clean_symbols} collected {len(all_articles)} unique articles.")
        return list(all_articles.values())

    def fetch_all_sources(self) -> List[NewsArticle]:
        """Комплексный сбор со всех источников (CryptoPanic + Google News RSS + RSS)."""
        all_articles: Dict[str, NewsArticle] = {}

        # 1. CryptoPanic
        cp_news = self.fetch_cryptopanic_news(limit=15)
        for a in cp_news:
            all_articles[a.content_hash] = a

        # 2. Поиск по ключевым темам через Google News Engine
        queries = [
            "Bitcoin BTC market price news today",
            "Ethereum ETH crypto regulation ETF news today",
            "Federal Reserve interest rates inflation crypto macro",
            "Solana crypto ecosystem breaking news",
        ]
        for q in queries:
            search_res = self.search_news(q, max_results=5)
            for a in search_res:
                all_articles[a.content_hash] = a

        # 3. RSS Ленты
        for feed in self.RSS_FEEDS:
            rss_news = self.fetch_rss_feed(feed["name"], feed["url"], limit=10)
            for a in rss_news:
                all_articles[a.content_hash] = a

        result = list(all_articles.values())
        logger.info(f"Total unique articles fetched: {len(result)}")
        return result
