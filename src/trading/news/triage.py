import os
import re
import time
import logging
from typing import Optional, Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.trading.news.models import NewsTriageResult, RawNewsItem

logger = logging.getLogger(__name__)

TRIAGE_SYSTEM_PROMPT = """You are an ultra-fast, quantitative Crypto News Triage Engine (HFT/Event-Driven).
Your task is to analyze incoming breaking news, headlines, and articles and evaluate their market impact in milliseconds.

CRITICAL RULES:
1. Extract the primary TRADABLE symbol (without USDT/USD, e.g. "BTC", "ETH", "SOL", "ENA", "SUI", "AAVE").
   - If the news is general macro without a specific coin, return symbol=null or "MACRO", is_tradable=false.
   - If there is a clear specific cryptocurrency affected, extract it and set is_tradable=true.
2. Assign impact_score from 1 (irrelevant noise) to 10 (massive market mover):
   - 9-10: Major Tier-1 Exchange Listing (Binance/Bybit/Coinbase), Critical Protocol Exploit/Hack ($20M+), Massive Regulatory Action (SEC approval/ban).
   - 7-8: Major Partnership with Tier-1 Tech (Google/Apple/Visa), Major Tokenomics/Staking Overhaul, Mainnet Launch, Founder departure/arrest.
   - 4-6: Mid-tier updates, minor integrations, price predictions by analysts, routine governance proposals.
   - 1-3: Generic articles, sponsored promo, recycled retrospective commentary, clickbait noise.
3. Classify sentiment: BULLISH, BEARISH, or NEUTRAL.
4. Classify event_type: LISTING, EXPLOIT, PARTNERSHIP, TOKENOMICS, REGULATORY, or NOISE.
5. Provide concise, high-density 1-sentence summaries in both English and Russian.
"""

# Известные катализаторы и маркеры для быстрого пре-фильтра (экономия квоты LLM)
CATALYST_KEYWORDS = {
    "LISTING": ["listing", "lists", "listed", "launch on", "perpetual", "futures listing"],
    "EXPLOIT": ["hack", "exploit", "exploited", "stolen", "drain", "drained", "vulnerability", "attack"],
    "PARTNERSHIP": ["partner", "partnership", "collaboration", "integrates", "visa", "mastercard", "google", "apple"],
    "TOKENOMICS": ["burn", "tokenomics", "staking", "unlock", "airdrop", "halving", "buyback", "treasury"],
    "REGULATORY": ["sec", "cftc", "lawsuit", "approval", "ban", "etf", "indictment", "court", "ruling", "fed", "cpi", "rate cut", "rate hike"],
}

KNOWN_TOP_COINS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK", "SUI",
    "ENA", "TON", "DOT", "NEAR", "APT", "UNI", "SHIB", "PEPE", "WIF", "RENDER",
    "TAO", "AAVE", "MKR", "ARB", "OP", "FET", "INJ", "TIA", "SEI", "KAS", "NOT"
}

class FastNewsTriageEngine:
    """
    Модуль ультра-быстрой LLM-сортировки новостей с защитой от лимитов квоты Gemini (15 RPM):
    1. Эвристический пре-фильтр (отсекает шум без вызова LLM)
    2. Скоростной ограничитель (Rate Limiter) с задержками
    3. Аварийный откат (Fallback) при 429 ошибке
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        self.model_name = os.getenv("TRIAGE_MODEL", "gemini-3.5-flash-lite")
        self._llm = None
        self._structured_llm = None
        self._last_request_time = 0.0
        self._min_request_interval = 4.2 # Безопасная пауза (макс 14 запросов в минуту)
        self._backoff_until = 0.0

    def _get_structured_llm(self):
        if self._structured_llm is None:
            self._llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=0.0,
                max_retries=1,
            )
            self._structured_llm = self._llm.with_structured_output(NewsTriageResult)
        return self._structured_llm

    def _quick_heuristic_check(self, title: str, content: str) -> Optional[NewsTriageResult]:
        """
        Мгновенный пре-фильтр без вызова LLM.
        Если новость является явным мусором/кликом без крипто-сущностей, не тратим квоту Gemini.
        """
        text = f"{title} {content}".lower()

        # Поиск совпадений монет
        detected_symbol = None
        for sym in KNOWN_TOP_COINS:
            pattern = rf"\b{sym.lower()}\b"
            if re.search(pattern, text):
                detected_symbol = sym
                break

        # Проверка наличия ключевых слов катализатора
        matched_category = None
        for cat, keywords in CATALYST_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                matched_category = cat
                break

        # Если нет ни монеты, ни ключевых слов -> очевидный шум, отсекаем БЕЗ вызова LLM
        if not detected_symbol and not matched_category:
            return NewsTriageResult(
                symbol=None,
                is_tradable=False,
                impact_score=1,
                sentiment="NEUTRAL",
                event_type="NOISE",
                summary_en=f"Filtered as background noise: {title[:80]}",
                summary_ru=f"Отфильтровано как фоновый шум: {title[:80]}",
            )

        return None

    def triage_news(self, news: RawNewsItem) -> NewsTriageResult:
        """
        Оценка новости с пре-фильтрацией и защитой от квоты 15 RPM.
        """
        # 1. Быстрый пре-фильтр (Zero LLM Tokens)
        quick_res = self._quick_heuristic_check(news.title, news.content)
        if quick_res is not None:
            return quick_res

        # 2. Проверка активного периода 429 backoff
        now = time.time()
        if now < self._backoff_until:
            logger.debug(f"Gemini quota cooldown active, using smart heuristic triage for: {news.title[:50]}")
            return self._heuristic_fallback(news)

        # 3. Rate limiter pause
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)

        t0 = time.time()
        user_prompt = f"""EVALUATE THIS BREAKING CRYPTO NEWS:
Title: {news.title}
Content / Summary: {news.content or 'No extra body text'}
Source: {news.source}
URL: {news.url}
Published: {news.published_at}
"""
        try:
            structured_llm = self._get_structured_llm()
            messages = [
                SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
            self._last_request_time = time.time()
            result: NewsTriageResult = structured_llm.invoke(messages)
            elapsed_ms = round((time.time() - t0) * 1000, 1)
            logger.info(
                f"News Triage completed in {elapsed_ms}ms: [{result.symbol or 'N/A'}] "
                f"Impact={result.impact_score}/10 Type={result.event_type} Sentiment={result.sentiment}"
            )
            return result

        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                logger.warning(f"Gemini 429 Quota limit hit (15 RPM). Activating 20s cooldown and heuristic fallback.")
                self._backoff_until = time.time() + 20.0
            else:
                logger.error(f"Error in FastNewsTriageEngine LLM call: {e}")

            return self._heuristic_fallback(news)

    def _heuristic_fallback(self, news: RawNewsItem) -> NewsTriageResult:
        """Интеллектуальный аварийный классификатор на правилах."""
        text = f"{news.title} {news.content}".lower()

        symbol = None
        for sym in KNOWN_TOP_COINS:
            if re.search(rf"\b{sym.lower()}\b", text):
                symbol = sym
                break

        impact = 4
        event_type = "NOISE"
        sentiment = "NEUTRAL"

        if any(w in text for w in ["hack", "exploit", "stolen", "drain", "security breach"]):
            impact = 8
            event_type = "EXPLOIT"
            sentiment = "BEARISH"
        elif any(w in text for w in ["listing", "lists", "launch on", "perpetual", "futures"]):
            impact = 8
            event_type = "LISTING"
            sentiment = "BULLISH"
        elif any(w in text for w in ["partnership", "partners with", "collab", "visa"]):
            impact = 7
            event_type = "PARTNERSHIP"
            sentiment = "BULLISH"
        elif any(w in text for w in ["sec", "etf approval", "court ruling", "cpi", "rate cut"]):
            impact = 7
            event_type = "REGULATORY"
            sentiment = "BULLISH" if "approval" in text or "cut" in text else "NEUTRAL"
        elif any(w in text for w in ["burn", "staking", "tokenomics"]):
            impact = 6
            event_type = "TOKENOMICS"
            sentiment = "BULLISH"

        return NewsTriageResult(
            symbol=symbol,
            is_tradable=(symbol is not None),
            impact_score=impact,
            sentiment=sentiment,
            event_type=event_type,
            summary_en=f"Catalyst detected for {symbol or 'market'}: {news.title[:100]}",
            summary_ru=f"Катализатор для {symbol or 'рынка'}: {news.title[:100]}",
        )

_triage_engine_instance: Optional[FastNewsTriageEngine] = None

def get_triage_engine() -> FastNewsTriageEngine:
    global _triage_engine_instance
    if _triage_engine_instance is None:
        _triage_engine_instance = FastNewsTriageEngine()
    return _triage_engine_instance

